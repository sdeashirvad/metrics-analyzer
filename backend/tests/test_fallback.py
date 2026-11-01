import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from snowflake.connector.errors import OperationalError

from app.config import Settings
from app.db.connection import ReadTimeout, begin_read_deadline, end_read_deadline, fetch_all
from app.fallback.assets import ROOT, read_json
from app.fallback.catalog import control_desks, overview
from app.fallback.gates import Gate, snowflake_gate
from app.main import create_app


def _client() -> TestClient:
    snowflake_gate.reset()
    return TestClient(create_app(Settings(snowflake_account="account", snowflake_user="user", snowflake_password="secret")))


def test_manifest_matches_packaged_files():
    manifest = read_json("manifest")
    assert manifest["dqDatasetVersion"] == 1
    assert manifest["dqObservationDate"] == "2026-10-28"
    assert "portfolio" in manifest["portfolioRole"].lower()
    for relative in manifest["files"]:
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        json.loads(text)
        lowered = text.lower()
        assert "snowflake_password" not in lowered
        assert "private_key" not in lowered


def test_packaged_baseline_and_empty_desks():
    portfolio = read_json("dq-portfolio")
    assert portfolio["controls"] == 36
    assert portfolio["latest"] == {"red": 5, "amber": 2, "green": 29}
    assert portfolio["openExceptions"] == 722
    weekly = [row for row in portfolio["latestByControl"] if row["frequency"] == "Weekly"]
    assert len(weekly) == 6
    assert {row["asOf"] for row in weekly} == {"2026-10-23"}
    dq020 = next(row for row in portfolio["latestByControl"] if row["id"] == "DQ-020")
    assert dq020["passRate"] == 98.178
    assert dq020["failed"] == 3161
    assert dq020["total"] == 173463
    desks = {row["controlId"] for row in read_json("dq-desks")}
    assert desks == set(portfolio["deskControls"])
    assert len(desks) == 8
    body = overview()
    assert body["origin"] == "packaged_fallback"
    assert body["controls"] == 36
    empty = control_desks("DQ-007", None)
    assert empty["available"] is False
    assert empty["rows"] == []
    split = control_desks("DQ-020", "2026-10-28")
    assert split["available"] is True
    assert split["rows"]


def test_snowflake_outage_serves_package_and_unknown_stays_404(monkeypatch):
    calls = {"n": 0}

    @contextmanager
    def broken(_settings):
        calls["n"] += 1
        raise OperationalError(msg="warehouse unavailable")
        yield None

    monkeypatch.setattr("app.dq.router.connect_read", broken)
    snowflake_gate.reset()
    client = _client()
    first = client.get("/api/v1/dq/overview")
    second = client.get("/api/v1/dq/overview")
    missing = client.get("/api/v1/dq/controls/DQ-999")
    assert first.status_code == 200
    assert first.json()["origin"] == "packaged_fallback"
    assert first.json()["openExceptions"] == 722
    assert second.status_code == 200
    assert calls["n"] == 1
    assert missing.status_code == 404
    summary = client.get("/api/v1/dq/controls/DQ-020/analyses/summary")
    assert summary.status_code == 200
    assert summary.json()["source"] == "deterministic"
    assert "Not a Snowflake Cortex" in summary.json()["disclaimer"]
    assert calls["n"] == 1


def test_application_404_does_not_open_the_breaker(monkeypatch):
    @contextmanager
    def connected(_settings):
        yield object()

    monkeypatch.setattr("app.dq.router.connect_read", connected)

    def missing(_connection, _settings, _control_id):
        from app.core.errors import not_found

        raise not_found()

    monkeypatch.setattr("app.dq.service.control_detail", missing)
    snowflake_gate.reset()
    client = _client()
    response = client.get("/api/v1/dq/controls/DQ-999")
    assert response.status_code == 404
    assert snowflake_gate.allow() == "primary"


def test_shared_deadline_stops_before_another_statement():
    token = begin_read_deadline(-1)
    try:
        with pytest.raises(ReadTimeout):
            fetch_all(object(), "select 1")
    finally:
        end_read_deadline(token)


def test_gate_probe_is_single():
    gate = Gate(30)
    assert gate.allow() == "primary"
    gate.fail()
    assert gate.allow() == "fallback"
    gate._open_until = 0.1
    assert gate.allow() == "probe"
    assert gate.allow() == "fallback"
    gate.succeed()
    assert gate.allow() == "primary"


def test_technology_risk_does_not_open_snowflake(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("Technology Risk must not open Snowflake")

    monkeypatch.setattr("app.db.connection.connect", refuse)
    monkeypatch.setattr("app.db.connection.connect_read", refuse)
    client = _client()
    listed = client.get("/api/v1/tr/metrics")
    assert listed.status_code == 200
    ids = [item["metric"]["id"] for item in listed.json()["items"]]
    assert "M001" in ids and "M010" in ids
    detail = client.get("/api/v1/tr/metrics/M001")
    assert detail.status_code == 200
    assert detail.json()["reading"]["origin"] == "illustrative_synthetic"
    org = client.get("/api/v1/tr/metrics/M001/org")
    assert org.status_code == 200
    assert org.json()["origin"] == "illustrative_synthetic"
    missing = client.get("/api/v1/tr/metrics/M009/investigation")
    assert missing.status_code == 404
