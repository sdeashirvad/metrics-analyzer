"""Packaged Data Quality responses. Each call reads only the files that response needs."""

from __future__ import annotations

from app.core.errors import not_found
from app.dq.mapping import DESK_NOTE, desk_breakdown, desk_names_in, detail, discrepancy_sentence, list_item
from app.dq.service import _matches, parse_page
from app.fallback.assets import read_json
from app.fallback.facts import deterministic_investigation, deterministic_summary

_STATUS_RANK = {"red": 0, "amber": 1, "insufficient_data": 2, "green": 3}


def _portfolio() -> dict:
    return read_json("dq-portfolio")


def _definitions() -> list[dict]:
    return read_json("dq-definitions")


def _hierarchy() -> dict[str, dict]:
    return {row["id"]: row for row in read_json("dq-hierarchy")}


def _control_map() -> dict[str, dict]:
    portfolio = _portfolio()
    latest = {row["id"]: row for row in portfolio["latestByControl"]}
    stories = {row["id"]: row["readme"] for row in portfolio["stories"]}
    desks = set(portfolio["deskControls"])
    records = {}
    for definition in _definitions():
        snap = latest.get(definition["id"])
        records[definition["id"]] = {
            "id": definition["id"],
            "name": definition["name"],
            "dimension": definition["dimension"],
            "frequency": definition["frequency"],
            "green": definition["green"],
            "amber": definition["amber"],
            "severity": definition["severity"],
            "checkLogic": definition["checkLogic"],
            "owner": definition["owner"],
            "regulation": definition["regulation"],
            "report": definition["report"],
            "cde": definition["cde"],
            "sourceSystem": definition["sourceSystem"],
            "principle": definition["principle"],
            "plantedStory": stories.get(definition["id"]),
            "snapshotUnavailable": snap is None,
            "controlDataVersion": 1 if snap else None,
            "datasetVersion": 1 if snap else None,
            "calculationVersion": "dq-rag-v1" if snap else None,
            "passRate": None if snap is None else snap["passRate"],
            "status": "insufficient_data" if snap is None else snap["status"],
            "failed": None if snap is None else snap["failed"],
            "total": None if snap is None else snap["total"],
            "asOf": None if snap is None else snap["asOf"],
            "firstRed": None if snap is None else snap.get("firstRed"),
            "lastRed": None if snap is None else snap.get("lastRed"),
            "pointCount": None if snap is None else snap.get("points"),
            "hasDeskSplit": definition["id"] in desks,
            "recovered": bool(snap and snap.get("firstRed") and snap.get("status") == "green"),
            "openExceptions": 0,
            "exceptionCount": 0,
            "oldestOpenAge": None,
            "eventCount": 0,
            "commentaryCount": 0,
        }
    return records


def _require(control_id: str) -> dict:
    found = _control_map().get(control_id)
    if not found:
        raise not_found()
    return found


def _with_counts(control: dict) -> dict:
    control = dict(control)
    exceptions = [row for row in read_json("dq-exceptions") if row["controlId"] == control["id"]]
    open_rows = [row for row in exceptions if row["status"] == "Open"]
    control["exceptionCount"] = len(exceptions)
    control["openExceptions"] = len(open_rows)
    control["oldestOpenAge"] = max((row["ageingDays"] for row in open_rows), default=None)
    control["eventCount"] = sum(1 for row in read_json("dq-events") if row["controlId"] == control["id"])
    control["commentaryCount"] = sum(1 for row in read_json("dq-commentary") if row["controlId"] == control["id"])
    return control


def _stamp(payload: dict) -> dict:
    payload = dict(payload)
    payload["origin"] = "packaged_fallback"
    return payload


def overview() -> dict:
    portfolio = _portfolio()
    controls = list(_control_map().values())
    names = [row["name"] for row in read_json("dq-hierarchy")]
    commentary: dict[str, list[str]] = {}
    for row in read_json("dq-commentary"):
        commentary.setdefault(row["controlId"], []).append(row["text"])
    discrepancies = []
    for item in controls:
        if not item["plantedStory"]:
            continue
        sentence = discrepancy_sentence(
            item["id"],
            desk_names_in(item["plantedStory"], names),
            desk_names_in("\n".join(commentary.get(item["id"], [])), names),
        )
        if sentence:
            discrepancies.append(sentence)
    at_risk = []
    events = read_json("dq-events")
    event_counts: dict[str, int] = {}
    for event in events:
        event_counts[event["controlId"]] = event_counts.get(event["controlId"], 0) + 1
    for item in controls:
        if item["snapshotUnavailable"]:
            continue
        if item["status"] in {"red", "amber"} or (item["plantedStory"] and item["firstRed"]):
            at_risk.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "dimension": item["dimension"],
                    "status": item["status"],
                    "passRate": item["passRate"],
                    "failed": item["failed"],
                    "total": item["total"],
                    "asOf": item["asOf"],
                    "firstRed": item["firstRed"],
                    "lastRed": item["lastRed"],
                    "recovered": item["recovered"],
                    "hasDeskSplit": item["hasDeskSplit"],
                    "investigationAvailable": bool(item["plantedStory"]),
                    "eventCount": event_counts.get(item["id"], 0),
                    "readme": item["plantedStory"],
                }
            )
    at_risk.sort(
        key=lambda item: (
            int(bool(item["recovered"])),
            _STATUS_RANK.get(item["status"], 9),
            item["firstRed"] or "9999-99-99",
            item["id"],
        )
    )
    return _stamp(
        {
            "asOf": portfolio["asOf"],
            "dateFrom": portfolio["dateFrom"],
            "dateTo": portfolio["dateTo"],
            "controls": portfolio["controls"],
            "withResults": portfolio["withResults"],
            "latest": portfolio["latest"],
            "openExceptions": portfolio["openExceptions"],
            "byDimension": portfolio["byDimension"],
            "hotspots": portfolio["hotspots"],
            "stories": portfolio["stories"],
            "deskNote": DESK_NOTE,
            "atRisk": at_risk,
            "events": [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "type": row["type"],
                    "controlId": row["controlId"],
                    "description": row["description"],
                }
                for row in events
            ],
            "coverage": {
                **portfolio["coverage"],
                "discrepancy": " ".join(discrepancies)
                if discrepancies
                else "Desk names in planted stories and commentary were compared. No disagreement was found.",
            },
        }
    )


def control_list(**kwargs) -> dict:
    page, page_size = parse_page(kwargs["page"], kwargs["page_size"])
    controls = list(_control_map().values())
    items = [list_item(item, bool(item["plantedStory"])) for item in controls]
    domains = []
    for item in items:
        if item["metric"]["domain"] not in domains:
            domains.append(item["metric"]["domain"])
    filtered = [
        item
        for item in items
        if _matches(item, kwargs["q"], kwargs["domain"], kwargs["status"], kwargs["frequency"], kwargs["investigation"])
    ]
    filtered.sort(
        key=lambda item: (
            _STATUS_RANK.get(item["reading"]["status"], 9),
            item["reading"]["breachedOn"] or "9999-99-99",
            item["metric"]["id"],
        )
    )
    start = (page - 1) * page_size
    frequencies = [value for value in ("Daily", "Weekly", "Monthly") if any(item["metric"]["frequency"] == value for item in items)]
    return _stamp(
        {
            "items": filtered[start : start + page_size],
            "total": len(filtered),
            "page": page,
            "pageSize": page_size,
            "facets": {
                "domains": domains,
                "frequencies": frequencies,
                "statuses": ["red", "amber", "green", "insufficient_data"],
                "families": ["data_quality"],
                "domainsByFamily": {"technology_risk": [], "data_quality": domains},
            },
        }
    )


def _series(control_id: str, limit: int | None = None) -> list[dict]:
    rows = [row for row in read_json("dq-results") if row["controlId"] == control_id]
    rows.sort(key=lambda row: row["date"])
    if limit is not None:
        rows = rows[-limit:]
    return [
        {
            "date": row["date"],
            "passRate": row["passRate"],
            "status": row["status"],
            "failed": row["failed"],
            "total": row["total"],
        }
        for row in rows
    ]


def control_detail(control_id: str) -> dict:
    control = _require(control_id)
    series = [] if control["snapshotUnavailable"] else _series(control_id)
    return _stamp(detail(control, series, bool(control["plantedStory"])))


def control_trend(control_id: str) -> dict:
    control = _require(control_id)
    series = [] if control["snapshotUnavailable"] else _series(control_id, 20)
    return _stamp(
        {
            "metricId": control_id,
            "origin": "workbook",
            "caption": "Workbook pass rate from dq_results. Status is the supplied RAG.",
            "points": [
                {
                    "date": row["date"],
                    "value": row["passRate"],
                    "status": row["status"],
                    "origin": "workbook",
                    "unconfirmedAmber": False,
                    "pointNote": "Supplied dq_results row.",
                }
                for row in series
            ],
        }
    )


def control_desks(control_id: str, metric_date: str | None) -> dict:
    control = _require(control_id)
    if not control["hasDeskSplit"]:
        return _stamp(desk_breakdown(control_id, has_desk_split=False, rows=[], requested_date=metric_date))
    names = _hierarchy()
    rows = [row for row in read_json("dq-desks") if row["controlId"] == control_id]
    if metric_date:
        rows = [row for row in rows if row["date"] == metric_date]
    elif rows:
        latest = max(row["date"] for row in rows)
        rows = [row for row in rows if row["date"] == latest]
    failed_sum = sum(int(row["failed"]) for row in rows) or 1
    mapped = [
        {
            "deskId": row["deskId"],
            "deskName": names.get(row["deskId"], {}).get("name") or row["deskId"],
            "line": names.get(row["deskId"], {}).get("line"),
            "region": names.get(row["deskId"], {}).get("region"),
            "date": row["date"],
            "failed": row["failed"],
            "total": row["total"],
            "passRate": row["passRate"],
            "status": row["status"],
            "shareOfFailures": round(100 * int(row["failed"]) / failed_sum, 1),
        }
        for row in rows
    ]
    mapped.sort(key=lambda row: (-row["failed"], row["deskId"]))
    return _stamp(desk_breakdown(control_id, has_desk_split=True, rows=mapped, requested_date=metric_date))


def control_exceptions(control_id: str, status: str | None, page: int, page_size: int) -> dict:
    _require(control_id)
    page, page_size = parse_page(page, page_size)
    names = _hierarchy()
    rows = [row for row in read_json("dq-exceptions") if row["controlId"] == control_id]
    statuses = sorted({row["status"] for row in rows})
    if status:
        rows = [row for row in rows if row["status"] == status]
    rows.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    start = (page - 1) * page_size
    return _stamp(
        {
            "total": len(rows),
            "page": page,
            "pageSize": page_size,
            "statuses": statuses,
            "items": [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "controlId": row["controlId"],
                    "deskId": row["deskId"],
                    "deskName": names.get(row["deskId"], {}).get("name") or row["deskId"],
                    "tradeId": row["tradeId"],
                    "field": row["field"],
                    "value": row["value"],
                    "reason": row["reason"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "ageingDays": row["ageingDays"],
                    "team": row["team"],
                }
                for row in rows[start : start + page_size]
            ],
        }
    )


def control_notes(control_id: str) -> dict:
    _require(control_id)
    return _stamp(
        {
            "events": [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "type": row["type"],
                    "deskIds": row["deskIds"],
                    "description": row["description"],
                }
                for row in read_json("dq-events")
                if row["controlId"] == control_id
            ],
            "commentary": [
                {
                    "date": row["date"],
                    "ragAtTime": row["ragAtTime"],
                    "text": row["text"],
                    "cause": row["cause"],
                    "path": row["path"],
                    "author": row["author"],
                }
                for row in read_json("dq-commentary")
                if row["controlId"] == control_id
            ],
        }
    )


def metadata() -> dict:
    portfolio = _portfolio()
    return _stamp(
        {
            "datasetVersion": 1,
            "dateFrom": portfolio["dateFrom"],
            "dateTo": portfolio["dateTo"],
            "calculationVersion": "dq-rag-v1",
            "sourceLabel": "Packaged Data Quality snapshot",
        }
    )


def summary_for(control_id: str) -> dict:
    return _stamp(deterministic_summary(_require(control_id)))


def investigation_for(control_id: str) -> dict:
    control = _with_counts(_require(control_id))
    notes = control_notes(control_id)
    desks = control_desks(control_id, control.get("asOf"))
    notes.pop("origin", None)
    desks.pop("origin", None)
    payload = deterministic_investigation(control, desks, notes)
    return _stamp(payload)
