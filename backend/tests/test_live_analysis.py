import pytest

from app.analysis.service import cached_analysis, run_analysis
from app.config import load_settings
from app.core.errors import AppError
from app.db.analyses import insert_run
from app.db.connection import connect, fetch_one
from app.db.controls import get_control
from app.jobs.refresh_summaries import refresh_at_risk

pytestmark = pytest.mark.live


def test_cache_hit_does_not_call_the_agent(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("agent was called")

    monkeypatch.setattr("app.analysis.service.run_agent", fail)
    settings = load_settings()
    with connect(settings) as connection:
        result = run_analysis(connection, settings, "DQ-020", "SUMMARY", False)
    assert result["cached"] is True
    assert result["text"]


def test_force_refresh_appends_a_row():
    settings = load_settings()
    with connect(settings) as connection:
        before = fetch_one(
            connection,
            f"""
            SELECT COUNT(*) AS N FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
            WHERE CONTROL_ID = 'DQ-020' AND ANALYSIS_TYPE = 'SUMMARY' AND STATUS = 'COMPLETED'
            """,
        )
        result = run_analysis(connection, settings, "DQ-020", "SUMMARY", True)
        after = fetch_one(
            connection,
            f"""
            SELECT COUNT(*) AS N FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
            WHERE CONTROL_ID = 'DQ-020' AND ANALYSIS_TYPE = 'SUMMARY' AND STATUS = 'COMPLETED'
            """,
        )
    assert result["cached"] is False
    assert int(after["N"]) == int(before["N"]) + 1


def test_stale_control_version_is_ignored():
    settings = load_settings()
    with connect(settings) as connection:
        control = get_control(connection, settings, "DQ-020")
        insert_run(
            connection,
            settings,
            control_id="DQ-020",
            analysis_type="SUMMARY",
            control_data_version=999999,
            dataset_version=control["datasetVersion"] or 0,
            prompt_version="summary-v1",
            calculation_version=control["calculationVersion"],
            status="COMPLETED",
            result={"narrative": {}, "response": {"text": "STALE VERSION", "controlId": "DQ-020"}},
            error_text=None,
        )
        found = cached_analysis(connection, settings, "DQ-020", "SUMMARY")
    assert found["text"] != "STALE VERSION"


def test_invalid_json_is_stored_failed(monkeypatch):
    monkeypatch.setattr("app.analysis.service.run_agent", lambda *_args, **_kwargs: "not json")
    settings = load_settings()
    with connect(settings) as connection:
        with pytest.raises(AppError) as caught:
            run_analysis(connection, settings, "DQ-003", "SUMMARY", True)
        row = fetch_one(
            connection,
            f"""
            SELECT STATUS, RESULT FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
            WHERE CONTROL_ID = 'DQ-003' AND ANALYSIS_TYPE = 'SUMMARY'
            ORDER BY GENERATED_AT DESC
            LIMIT 1
            """,
        )
    assert caught.value.status_code == 502
    assert row["STATUS"] == "FAILED"
    assert row["RESULT"] is None


def test_at_risk_refresh_fills_seven_then_creates_none():
    first = refresh_at_risk()
    second = refresh_at_risk()
    assert first["selected"] == 7
    assert first["failed"] == 0
    assert first["created"] + first["skipped"] == 7
    assert second["created"] == 0
    assert second["skipped"] == 7
    assert second["failed"] == 0
