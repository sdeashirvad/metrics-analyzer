from app.config import Settings
from app.core.errors import bad_request, not_found
from app.db.controls import get_control, list_controls
from app.db.desks import desks as load_desks
from app.db.desks import hotspots
from app.db.evidence import notes as load_notes
from app.db.exceptions import page as exception_page
from app.db.history import history, recent_for
from app.db.portfolio import coverage, dataset, desk_names, open_exception_count
from app.db.portfolio import completed_investigation_ids
from app.dq.mapping import DESK_NOTE, desk_breakdown, desk_names_in, detail, discrepancy_sentence, list_item

_STATUS_RANK = {"red": 0, "amber": 1, "insufficient_data": 2, "green": 3}


def overview(connection, settings: Settings) -> dict:
    controls = list_controls(connection, settings)
    state = dataset(connection, settings) or {}
    investigated = completed_investigation_ids(connection, settings)
    names = desk_names(connection, settings)
    commentary = _commentary_by_control(connection, settings)
    countable = [item for item in controls if not item["snapshotUnavailable"]]
    latest = {"red": 0, "amber": 0, "green": 0}
    by_dimension: dict[str, dict[str, int]] = {}
    for item in countable:
        if item["status"] in latest:
            latest[item["status"]] += 1
        bucket = by_dimension.setdefault(item["dimension"], {"name": item["dimension"], "red": 0, "amber": 0, "green": 0})
        if item["status"] in bucket:
            bucket[item["status"]] += 1
    story_ids = [item["id"] for item in controls if item["plantedStory"]]
    recent = recent_for(connection, settings, story_ids, 20)
    stories = []
    discrepancies = []
    for item in controls:
        if not item["plantedStory"]:
            continue
        story_names = desk_names_in(item["plantedStory"], names)
        note_names = desk_names_in("\n".join(commentary.get(item["id"], [])), names)
        sentence = discrepancy_sentence(item["id"], story_names, note_names)
        if sentence:
            discrepancies.append(sentence)
        stories.append(
            {
                "id": item["id"],
                "name": item["name"],
                "readme": item["plantedStory"],
                "status": item["status"],
                "asOf": item["asOf"],
                "passRate": item["passRate"],
                "failed": item["failed"],
                "total": item["total"],
                "firstRed": item["firstRed"],
                "recent": recent.get(item["id"], []),
            }
        )
    at_risk = []
    for item in countable:
        planted = bool(item["plantedStory"])
        if item["status"] in {"red", "amber"} or (planted and item["firstRed"]):
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
                    "investigationAvailable": planted or item["id"] in investigated,
                    "eventCount": item["eventCount"],
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
    covered = coverage(connection, settings)
    events = _events(connection, settings)
    return {
        "asOf": state.get("dateTo") or "",
        "dateFrom": state.get("dateFrom") or "",
        "dateTo": state.get("dateTo") or "",
        "controls": len(controls),
        "withResults": len(countable),
        "latest": latest,
        "openExceptions": open_exception_count(connection, settings),
        "byDimension": [by_dimension[name] for name in sorted(by_dimension)],
        "hotspots": hotspots(connection, settings),
        "stories": stories,
        "deskNote": DESK_NOTE,
        "atRisk": at_risk,
        "events": events,
        "coverage": {
            **covered,
            "discrepancy": " ".join(discrepancies)
            if discrepancies
            else "Desk names in planted stories and commentary were compared. No disagreement was found.",
        },
    }


def control_list(
    connection,
    settings: Settings,
    *,
    q: str | None,
    domain: str | None,
    status: str | None,
    frequency: str | None,
    investigation: bool | None,
    page: int,
    page_size: int,
) -> dict:
    controls = list_controls(connection, settings)
    investigated = completed_investigation_ids(connection, settings)
    items = [_with_flag(item, investigated) for item in controls]
    domains = []
    for item in items:
        if item["metric"]["domain"] not in domains:
            domains.append(item["metric"]["domain"])
    filtered = [item for item in items if _matches(item, q, domain, status, frequency, investigation)]
    filtered.sort(key=lambda item: (_STATUS_RANK.get(item["reading"]["status"], 9), item["reading"]["breachedOn"] or "9999-99-99", item["metric"]["id"]))
    start = (page - 1) * page_size
    frequencies = [value for value in ("Daily", "Weekly", "Monthly") if any(item["metric"]["frequency"] == value for item in items)]
    return {
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


def control_detail(connection, settings: Settings, control_id: str) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    series = history(connection, settings, control_id) if not control["snapshotUnavailable"] else []
    investigated = completed_investigation_ids(connection, settings)
    return detail(control, series, bool(control["plantedStory"]) or control_id in investigated)


def control_trend(connection, settings: Settings, control_id: str) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    series = [] if control["snapshotUnavailable"] else history(connection, settings, control_id, limit=20)
    points = [
        {
            "date": row["date"],
            "value": row["passRate"],
            "status": row["status"],
            "origin": "workbook",
            "unconfirmedAmber": False,
            "pointNote": "Supplied dq_results row.",
        }
        for row in series
    ]
    return {
        "metricId": control_id,
        "origin": "workbook",
        "caption": "Workbook pass rate from dq_results. Status is the supplied RAG.",
        "points": points,
    }


def control_desks(connection, settings: Settings, control_id: str, metric_date: str | None) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    if not control["hasDeskSplit"]:
        return desk_breakdown(control_id, has_desk_split=False, rows=[], requested_date=metric_date)
    rows = load_desks(connection, settings, control_id, metric_date)
    return desk_breakdown(control_id, has_desk_split=True, rows=rows, requested_date=metric_date)


def control_exceptions(connection, settings: Settings, control_id: str, status: str | None, page: int, page_size: int) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    return exception_page(connection, settings, control_id, status, page, page_size)


def control_notes(connection, settings: Settings, control_id: str) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    return load_notes(connection, settings, control_id)


def metadata(connection, settings: Settings) -> dict:
    state = dataset(connection, settings) or {}
    return {
        "datasetVersion": state.get("datasetVersion"),
        "dateFrom": state.get("dateFrom"),
        "dateTo": state.get("dateTo"),
        "calculationVersion": settings.calculation_version,
        "sourceLabel": state.get("sourceLabel"),
    }


def _with_flag(control: dict, investigated: set[str]) -> dict:
    return list_item(control, bool(control["plantedStory"]) or control["id"] in investigated)


def _matches(item: dict, q: str | None, domain: str | None, status: str | None, frequency: str | None, investigation: bool | None) -> bool:
    if domain and item["metric"]["domain"] != domain:
        return False
    if status and item["reading"]["status"] != status:
        return False
    if frequency and item["metric"]["frequency"] != frequency:
        return False
    if investigation and not item["investigationAvailable"]:
        return False
    if q:
        haystack = f"{item['metric']['id']} {item['metric']['name']} {item['metric']['domain']}".lower()
        if q.strip().lower() not in haystack:
            return False
    return True


def _commentary_by_control(connection, settings: Settings) -> dict[str, list[str]]:
    from app.db.connection import fetch_all

    rows = fetch_all(
        connection,
        f"""
        SELECT CONTROL_ID, ANALYST_COMMENTARY
        FROM {settings.qualified("ANALYST_COMMENTARY")}
        """,
    )
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["CONTROL_ID"], []).append(row["ANALYST_COMMENTARY"])
    return grouped


def _events(connection, settings: Settings) -> list[dict]:
    from app.db.connection import fetch_all
    from app.db.rows import iso

    rows = fetch_all(
        connection,
        f"""
        SELECT EVENT_ID, EVENT_DATE, EVENT_TYPE, RELATED_CONTROL_ID, DESCRIPTION
        FROM {settings.qualified("CHANGE_INCIDENT_EVENTS")}
        ORDER BY EVENT_DATE, EVENT_ID
        """,
    )
    return [
        {
            "id": row["EVENT_ID"],
            "date": iso(row["EVENT_DATE"]),
            "type": row["EVENT_TYPE"],
            "controlId": row["RELATED_CONTROL_ID"],
            "description": row["DESCRIPTION"],
        }
        for row in rows
    ]


def parse_page(page: int, page_size: int) -> tuple[int, int]:
    if page < 1 or page_size < 1 or page_size > 100:
        raise bad_request("page must be at least 1 and pageSize must be from 1 to 100.")
    return page, page_size
