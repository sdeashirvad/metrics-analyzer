import pytest

from app.analysis.service import run_analysis
from app.config import Settings
from app.core.errors import AppError


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


def test_contradictory_rag_is_stored_failed(monkeypatch):
    monkeypatch.setattr("app.analysis.service.get_control", lambda *_args, **_kwargs: _control())
    monkeypatch.setattr("app.analysis.service.history", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.analysis.service.load_notes", lambda *_args, **_kwargs: {"events": [], "commentary": []})
    monkeypatch.setattr("app.analysis.service.desk_names", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "app.analysis.service.run_agent",
        lambda *_args, **_kwargs: (
            '{"text":"The status is green.","movement":"Improved.","thresholdPosition":"Above the line.","implications":"None."}'
        ),
    )
    stored: dict = {}

    def insert(_connection, _settings, **kwargs):
        stored.update(kwargs)
        return "run-id"

    monkeypatch.setattr("app.analysis.service.analyses.insert_run", insert)
    settings = Settings(snowflake_account="account", snowflake_user="user", snowflake_password="secret")
    with pytest.raises(AppError) as caught:
        run_analysis(None, settings, "DQ-020", "SUMMARY", True)
    assert caught.value.status_code == 502
    assert stored["status"] == "FAILED"
    assert stored["result"] is None
