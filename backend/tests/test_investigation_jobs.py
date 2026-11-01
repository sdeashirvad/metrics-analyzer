import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.analysis import jobs
from app.analysis.service import begin_investigation, begin_summary, investigation_preview, operation_status
from app.config import Settings
from app.core.errors import AppError

GOOD = (
    '{"hypothesis":["Commentary may relate to the supplied result."],'
    '"implications":"The result sits against the stated threshold.",'
    '"validationSteps":["Read the supplied commentary path."]}'
)


def _control() -> dict:
    return {
        "id": "DQ-020",
        "name": "Name",
        "dimension": "Validity",
        "frequency": "Daily",
        "cde": "Field",
        "checkLogic": "Check",
        "owner": "Role",
        "green": 99.5,
        "amber": 98.0,
        "plantedStory": None,
        "passRate": 98.178,
        "status": "red",
        "failed": 3161,
        "total": 173463,
        "asOf": "2026-10-28",
        "firstRed": "2026-09-01",
        "lastRed": "2026-10-28",
        "recovered": False,
        "pointCount": 63,
        "openExceptions": 130,
        "exceptionCount": 200,
        "oldestOpenAge": 12,
        "hasDeskSplit": False,
        "snapshotUnavailable": False,
        "controlDataVersion": 1,
        "datasetVersion": 1,
        "calculationVersion": "dq-rag-v1",
    }


class Store:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def insert(self, _connection, _settings, **kwargs):
        run_id = str(uuid.uuid4())
        self.rows.append({**kwargs, "runId": run_id, "generatedAtValue": datetime.now(timezone.utc)})
        return run_id

    def _pack(self, row: dict) -> dict:
        return {
            "runId": row["runId"],
            "controlId": row["control_id"],
            "analysisType": row["analysis_type"],
            "controlDataVersion": row["control_data_version"],
            "datasetVersion": row["dataset_version"],
            "promptVersion": row["prompt_version"],
            "calculationVersion": row["calculation_version"],
            "model": "metrics-analyzer-dq-agent-v3",
            "status": row["status"],
            "result": row["result"],
            "errorText": row["error_text"],
            "generatedAt": row["generatedAtValue"].isoformat(),
            "generatedAtValue": row["generatedAtValue"],
        }

    def _same(self, row: dict, control_id: str, analysis_type: str, prompt_version: str) -> bool:
        return (
            row["control_id"] == control_id
            and row["analysis_type"] == analysis_type
            and row["prompt_version"] == prompt_version
            and row["status"] == "COMPLETED"
            and isinstance(row["result"], dict)
        )

    def find_completed(self, _connection, _settings, control_id, analysis_type, prompt_version):
        for row in reversed(self.rows):
            if self._same(row, control_id, analysis_type, prompt_version):
                return {
                    "runId": row["runId"],
                    "result": row["result"],
                    "generatedAt": row["generatedAtValue"].isoformat(),
                }
        return None

    def find_by_id(self, _connection, _settings, control_id, run_id):
        for row in self.rows:
            if row["runId"] == run_id and row["control_id"] == control_id:
                return self._pack(row)
        return None

    def _matches_operation(self, row: dict, operation_id: str) -> bool:
        if row["status"] == "COMPLETED" and isinstance(row["result"], dict):
            return row["result"].get("operationId") == operation_id
        if row["status"] == "FAILED":
            return str(row["error_text"] or "").startswith(f"op:{operation_id} ")
        return False

    def find_open_running(self, _connection, _settings, control_id, analysis_type, prompt_version, *_rest):
        running = [
            row
            for row in self.rows
            if row["control_id"] == control_id
            and row["analysis_type"] == analysis_type
            and row["prompt_version"] == prompt_version
            and row["status"] == "RUNNING"
            and not any(self._matches_operation(other, row["runId"]) for other in self.rows)
        ]
        if not running:
            return None
        return self._pack(running[-1])

    def find_terminal_for(self, _connection, _settings, operation_id):
        matches = [row for row in self.rows if self._matches_operation(row, operation_id)]
        if not matches:
            return None
        matches.sort(key=lambda row: (0 if row["status"] == "COMPLETED" else 1, row["generatedAtValue"]))
        return self._pack(matches[0])

    def find_latest_completed(self, _connection, _settings, control_id, analysis_type):
        completed = [
            row
            for row in self.rows
            if row["control_id"] == control_id
            and row["analysis_type"] == analysis_type
            and row["status"] == "COMPLETED"
            and isinstance(row["result"], dict)
        ]
        if not completed:
            return None
        row = completed[-1]
        return {
            "runId": row["runId"],
            "controlDataVersion": row.get("control_data_version"),
            "result": row["result"],
            "generatedAt": row["generatedAtValue"].isoformat(),
        }


@pytest.fixture()
def world(monkeypatch):
    store = Store()
    calls: list[str] = []

    @contextmanager
    def fake_connect(_settings):
        yield None

    monkeypatch.setattr("app.analysis.service.connect", fake_connect)
    monkeypatch.setattr("app.analysis.service.get_control", lambda *_args, **_kwargs: _control())
    monkeypatch.setattr("app.analysis.service.history", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.analysis.service.load_notes", lambda *_args, **_kwargs: {"events": [], "commentary": []})
    monkeypatch.setattr("app.analysis.service.desk_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.analysis.service.analyses.insert_run", store.insert)
    monkeypatch.setattr("app.analysis.service.analyses.find_completed", store.find_completed)
    monkeypatch.setattr("app.analysis.service.analyses.find_by_id", store.find_by_id)
    monkeypatch.setattr("app.analysis.service.analyses.find_open_running", store.find_open_running)
    monkeypatch.setattr("app.analysis.service.analyses.find_terminal_for", store.find_terminal_for)
    monkeypatch.setattr("app.analysis.service.analyses.find_latest_completed", store.find_latest_completed)
    from app.fallback.gates import cortex_gate, snowflake_gate

    cortex_gate.reset()
    snowflake_gate.reset()
    with jobs._GUARD:
        jobs._LIVE.clear()
        jobs._ORPHANS.clear()
        jobs._THREADS.clear()
        jobs._PENDING = 0
    return store, calls


def _settings() -> Settings:
    return Settings(snowflake_account="account", snowflake_user="user", snowflake_password="secret")


def _agent(calls, payload=GOOD, delay: threading.Event | None = None):
    def run(*_args, **_kwargs):
        calls.append("run")
        if delay is not None:
            assert delay.wait(3)
        if isinstance(payload, Exception):
            raise payload
        return payload

    return run


def test_fast_investigation_completes(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls))
    payload, code = begin_investigation(None, _settings(), "DQ-020", False)
    assert code == 202
    assert payload["status"] == "RUNNING"
    jobs.wait(payload["runId"], 3)
    done = operation_status(None, _settings(), "DQ-020", payload["runId"])
    assert done["status"] == "COMPLETED"
    assert done["result"]["kind"] == "data_quality"
    assert done["result"]["hypotheses"]
    assert done["result"]["whyItMatters"]
    assert calls == ["run"]
    assert [row["status"] for row in store.rows] == ["RUNNING", "COMPLETED"]


def test_slow_investigation_survives_reload_and_duplicate_requests(monkeypatch, world):
    _store, calls = world
    gate = threading.Event()
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, delay=gate))
    first, code = begin_investigation(None, _settings(), "DQ-020", False)
    assert code == 202
    for _ in range(50):
        if calls:
            break
        time.sleep(0.01)
    second, _second_code = begin_investigation(None, _settings(), "DQ-020", False)
    assert second["runId"] == first["runId"]
    current = operation_status(None, _settings(), "DQ-020", first["runId"])
    assert current["status"] == "RUNNING"
    assert calls == ["run"]
    gate.set()
    jobs.wait(first["runId"], 3)
    assert operation_status(None, _settings(), "DQ-020", first["runId"])["status"] == "COMPLETED"


def test_cache_hit_does_not_start_a_run(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls))
    store.rows.append(
        {
            "runId": "cached",
            "control_id": "DQ-020",
            "analysis_type": "INVESTIGATION",
            "control_data_version": 1,
            "dataset_version": 1,
            "prompt_version": "investigation-v1",
            "calculation_version": "dq-rag-v1",
            "status": "COMPLETED",
            "result": {"response": {"kind": "data_quality", "metricId": "DQ-020", "cached": False}},
            "error_text": None,
            "generatedAtValue": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
    )
    payload, code = begin_investigation(None, _settings(), "DQ-020", False)
    assert code == 200
    assert payload["cached"] is True
    assert calls == []


def test_force_refresh_starts_a_new_run_after_completion(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls))
    store.rows.append(
        {
            "runId": "cached",
            "control_id": "DQ-020",
            "analysis_type": "INVESTIGATION",
            "control_data_version": 1,
            "dataset_version": 1,
            "prompt_version": "investigation-v1",
            "calculation_version": "dq-rag-v1",
            "status": "COMPLETED",
            "result": {"response": {"kind": "data_quality", "metricId": "DQ-020"}},
            "error_text": None,
            "generatedAtValue": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
    )
    payload, code = begin_investigation(None, _settings(), "DQ-020", True)
    assert code == 202
    jobs.wait(payload["runId"], 3)
    assert operation_status(None, _settings(), "DQ-020", payload["runId"])["status"] == "COMPLETED"
    assert calls == ["run"]
    assert payload["runId"] != "cached"


def test_agent_failure_then_retry(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, payload=RuntimeError("nope")))
    failed, _code = begin_investigation(None, _settings(), "DQ-020", True)
    jobs.wait(failed["runId"], 3)
    status = operation_status(None, _settings(), "DQ-020", failed["runId"])
    assert status["status"] == "FAILED"
    assert status["result"] is None
    assert "nope" not in status["message"]
    assert any(row["status"] == "FAILED" and row["result"] is None for row in store.rows)
    cooled, cooled_code = begin_investigation(None, _settings(), "DQ-020", True)
    assert cooled_code == 200
    assert cooled["source"] == "deterministic"
    assert calls == ["run"]
    from app.fallback.gates import cortex_gate

    cortex_gate.reset()
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls))
    retried, code = begin_investigation(None, _settings(), "DQ-020", True)
    assert code == 202
    assert retried["runId"] != failed["runId"]
    jobs.wait(retried["runId"], 3)
    assert operation_status(None, _settings(), "DQ-020", retried["runId"])["status"] == "COMPLETED"


def test_malformed_agent_output_is_failed(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, payload="not json"))
    payload, _code = begin_investigation(None, _settings(), "DQ-020", True)
    jobs.wait(payload["runId"], 3)
    status = operation_status(None, _settings(), "DQ-020", payload["runId"])
    assert status["status"] == "FAILED"
    assert status["result"] is None
    assert "JSON" not in status["message"]
    failed = next(row for row in store.rows if row["status"] == "FAILED")
    assert failed["error_text"] == f"op:{payload['runId']} ValidationError"
    assert failed["result"] is None


def test_force_refresh_creates_a_separate_run_while_another_is_active(monkeypatch, world):
    store, calls = world
    gates = [threading.Event(), threading.Event()]
    order = threading.Lock()

    def agent(*_args, **_kwargs):
        with order:
            index = len(calls)
            calls.append(index)
        assert gates[index].wait(3)
        return GOOD

    monkeypatch.setattr("app.analysis.service.run_agent", agent)
    first, _code = begin_investigation(None, _settings(), "DQ-020", False)
    for _ in range(50):
        if calls:
            break
        time.sleep(0.01)
    second, code = begin_investigation(None, _settings(), "DQ-020", True)
    assert code == 202
    assert second["runId"] != first["runId"]
    gates[1].set()
    jobs.wait(second["runId"], 3)
    assert operation_status(None, _settings(), "DQ-020", first["runId"])["status"] == "RUNNING"
    finished = operation_status(None, _settings(), "DQ-020", second["runId"])
    assert finished["status"] == "COMPLETED"
    assert finished["runId"] == second["runId"]
    gates[0].set()
    jobs.wait(first["runId"], 3)
    assert operation_status(None, _settings(), "DQ-020", first["runId"])["status"] == "COMPLETED"
    linked = {row["result"]["operationId"] for row in store.rows if row["status"] == "COMPLETED"}
    assert linked == {first["runId"], second["runId"]}


def test_force_refresh_when_both_slots_are_occupied(monkeypatch, world):
    store, calls = world
    gate = threading.Event()
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, delay=gate))
    begin_investigation(None, _settings(), "DQ-020", True)
    begin_investigation(None, _settings(), "DQ-020", True)
    with pytest.raises(AppError) as caught:
        begin_investigation(None, _settings(), "DQ-020", True)
    assert caught.value.status_code == 429
    assert caught.value.code == "AGENT_BUSY"
    assert "Wait for one to finish" in caught.value.message
    from app.fallback.gates import cortex_gate

    assert cortex_gate.allow() == "primary"
    assert len([row for row in store.rows if row["status"] == "RUNNING"]) == 2
    gate.set()
    for row in store.rows:
        if row["status"] == "RUNNING":
            jobs.wait(row["runId"], 3)


def test_concurrent_normal_requests_join_one_run(monkeypatch, world):
    _store, calls = world
    gate = threading.Event()
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, delay=gate))
    found: list[str] = []

    def request() -> None:
        payload, code = begin_investigation(None, _settings(), "DQ-020", False)
        assert code == 202
        found.append(payload["runId"])

    threads = [threading.Thread(target=request) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
    assert len(set(found)) == 1
    gate.set()
    jobs.wait(found[0], 3)
    assert calls == ["run"]


def test_failed_run_stays_tied_to_its_operation_id(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, payload=RuntimeError("nope")))
    failed, _code = begin_investigation(None, _settings(), "DQ-020", True)
    jobs.wait(failed["runId"], 3)
    status = operation_status(None, _settings(), "DQ-020", failed["runId"])
    assert status["status"] == "FAILED"
    assert status["runId"] == failed["runId"]
    assert status["result"] is None
    matched = [row for row in store.rows if str(row["error_text"] or "").startswith(f"op:{failed['runId']} ")]
    assert len(matched) == 1
    assert matched[0]["result"] is None


def test_old_live_run_is_not_orphaned(monkeypatch, world):
    store, calls = world
    gate = threading.Event()
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, delay=gate))
    payload, _code = begin_investigation(None, _settings(), "DQ-020", False)
    for row in store.rows:
        if row["runId"] == payload["runId"]:
            row["generatedAtValue"] = datetime.now(timezone.utc) - timedelta(hours=2)
    assert jobs.is_active(payload["runId"])
    assert operation_status(None, _settings(), "DQ-020", payload["runId"])["status"] == "RUNNING"
    gate.set()
    jobs.wait(payload["runId"], 3)


def test_validation_failure_does_not_open_cortex_cooldown(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, payload="not json"))
    payload, _code = begin_investigation(None, _settings(), "DQ-020", True)
    jobs.wait(payload["runId"], 3)
    from app.fallback.gates import cortex_gate

    assert cortex_gate.allow() == "primary"
    begin_investigation(None, _settings(), "DQ-020", True)
    assert calls == ["run", "run"]
    for row in store.rows:
        if row["status"] == "RUNNING":
            jobs.wait(row["runId"], 3)


SUMMARY = (
    '{"text":"Pass rate is 98.178.",'
    '"movement":"Still red.",'
    '"thresholdPosition":"Below the line.",'
    '"implications":"3161 failed of 173463."}'
)


def test_summary_cache_async_and_previous_result(monkeypatch, world):
    store, calls = world
    monkeypatch.setattr("app.analysis.service.run_agent", _agent(calls, payload=SUMMARY))
    started, code = begin_summary(None, _settings(), "DQ-020", False)
    assert code == 202
    jobs.wait(started["runId"], 3)
    finished = operation_status(None, _settings(), "DQ-020", started["runId"])
    assert finished["status"] == "COMPLETED"
    assert finished["result"]["source"] == "cortex"
    cached, cached_code = begin_summary(None, _settings(), "DQ-020", False)
    assert cached_code == 200
    assert cached["cached"] is True
    assert cached["source"] == "cortex"
    assert calls == ["run"]
    def completed_for(operation_id: str) -> list[dict]:
        return [
            row
            for row in store.rows
            if row["status"] == "COMPLETED"
            and isinstance(row.get("result"), dict)
            and row["result"].get("operationId") == operation_id
        ]

    refreshed, refresh_code = begin_summary(None, _settings(), "DQ-020", True)
    assert refresh_code == 202
    assert refreshed["runId"] != started["runId"]
    assert len(completed_for(started["runId"])) == 1
    jobs.wait(refreshed["runId"], 3)
    assert len(completed_for(started["runId"])) == 1
    assert len(completed_for(refreshed["runId"])) == 1


def test_summary_cooldown_is_deterministic_and_not_cached(monkeypatch, world):
    store, calls = world
    from app.fallback.gates import cortex_gate

    cortex_gate.fail()
    before = len(store.rows)
    body, code = begin_summary(None, _settings(), "DQ-020", False)
    assert code == 200
    assert body["source"] == "deterministic"
    assert body["cached"] is False
    assert "Not a Snowflake Cortex" in body["disclaimer"]
    assert len(store.rows) == before
    assert calls == []


def test_preview_is_not_written(monkeypatch, world):
    store, _calls = world
    before = len(store.rows)
    fresh = investigation_preview(None, _settings(), "DQ-020")
    assert fresh["source"] == "deterministic"
    assert len(store.rows) == before
    store.rows.append(
        {
            "runId": "older",
            "control_id": "DQ-020",
            "analysis_type": "INVESTIGATION",
            "control_data_version": 0,
            "dataset_version": 1,
            "prompt_version": "investigation-v1",
            "calculation_version": "dq-rag-v1",
            "status": "COMPLETED",
            "result": {"response": {"kind": "data_quality", "metricId": "DQ-020", "summary": "earlier"}},
            "error_text": None,
            "generatedAtValue": datetime.now(timezone.utc) - timedelta(days=1),
        }
    )
    preview = investigation_preview(None, _settings(), "DQ-020")
    assert preview["source"] == "previous_cortex"
    assert preview["stale"] is True
    assert preview["summary"] == "earlier"
    assert len(store.rows) == 1
