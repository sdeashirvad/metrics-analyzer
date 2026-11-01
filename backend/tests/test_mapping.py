from app.dq.mapping import desk_breakdown, detail, established_lines, note_payload


def _definition_without_snapshot() -> dict:
    return {
        "id": "DQ-099",
        "name": "Unmeasured control",
        "dimension": "Validity",
        "frequency": "Daily",
        "green": 99.0,
        "amber": 97.0,
        "checkLogic": "Check the field",
        "owner": "Owner",
        "cde": "Field",
        "snapshotUnavailable": True,
        "passRate": None,
        "status": "insufficient_data",
        "failed": None,
        "total": None,
        "asOf": None,
        "firstRed": None,
        "lastRed": None,
        "hasDeskSplit": False,
        "openExceptions": None,
        "exceptionCount": None,
        "oldestOpenAge": None,
    }


def test_definition_without_snapshot_does_not_invent_a_reading():
    payload = detail(_definition_without_snapshot(), [], False)
    assert payload["snapshotUnavailable"] is True
    assert payload["reading"]["value"] is None
    assert payload["reading"]["asOf"] is None
    assert payload["reading"]["status"] == "insufficient_data"
    assert payload["reading"]["status"] != "green"
    assert "workbook" not in payload
    assert payload["trend"] == []
    assert "invented" in payload["coverageNote"]


def test_empty_desks_and_notes_stay_empty():
    desks = desk_breakdown("DQ-099", has_desk_split=False, rows=[], requested_date=None)
    missing_date = desk_breakdown("DQ-020", has_desk_split=True, rows=[], requested_date="2026-10-28")
    notes = note_payload()
    lines = established_lines(_definition_without_snapshot(), desks, notes)
    assert desks["available"] is False
    assert desks["rows"] == []
    assert missing_date["available"] is False
    assert missing_date["rows"] == []
    assert notes == {"events": [], "commentary": []}
    assert all("change or incident" not in line for line in lines)
    assert any("not invented" in line for line in lines)
