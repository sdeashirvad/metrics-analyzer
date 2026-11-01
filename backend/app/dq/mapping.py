"""Map Snowflake rows onto the shapes the React screens already render."""

from __future__ import annotations

DESK_NOTE = (
    "Desk rows exist for controls that have a desk split. Bars sum failed records on the latest shared date. "
    "A lower pass rate is not the same as a larger failure count."
)
NOT_SUPPLIED = (
    "A linked change or incident event is not a cause. The link is only the related control id on the event row."
)
SUMMARY_DISCLAIMER = (
    "Narrative fields come from the published Data Quality agent. Pass rate, RAG, counts, thresholds, and dates come from Snowflake."
)


def metric_definition(control: dict) -> dict:
    return {
        "id": control["id"],
        "name": control["name"],
        "domain": control["dimension"],
        "controlId": control["id"],
        "frequency": control["frequency"],
        "direction": "higher_is_better",
        "unit": "%",
        "thresholds": {"green": control["green"], "amber": control["amber"]},
        "provisionalDefinition": control["checkLogic"],
        "definitionStatus": "provisional_pending_validation",
        "ownerFunction": control["owner"],
        "controlStatement": control["checkLogic"],
    }


def reading(control: dict) -> dict:
    # The handover named this state UNKNOWN. The finalized API enum is
    # insufficient_data, which is the status the UI already renders, plus
    # snapshotUnavailable: true. No UNKNOWN badge is added.
    if control["snapshotUnavailable"]:
        return {
            "value": None,
            "asOf": None,
            "origin": "workbook",
            "status": "insufficient_data",
            "statusBasis": "workbook_rag",
            "breachedOn": None,
        }
    return {
        "value": control["passRate"],
        "asOf": control["asOf"],
        "origin": "workbook",
        "status": control["status"],
        "statusBasis": "workbook_rag",
        "breachedOn": control["firstRed"],
    }


def trend_points(rows: list[dict]) -> list[dict]:
    return [
        {
            "date": row["date"],
            "value": row["passRate"],
            "status": row["status"],
            "origin": "workbook",
            "unconfirmedAmber": False,
            "pointNote": "Supplied dq_results row. The RAG value is the workbook status. Missing dates are not filled.",
        }
        for row in rows
    ]


def list_item(control: dict, investigation_available: bool) -> dict:
    return {
        "family": "data_quality",
        "investigationAvailable": investigation_available,
        "metric": metric_definition(control),
        "reading": reading(control),
    }


def detail(control: dict, series: list[dict], investigation_available: bool) -> dict:
    points = trend_points(series)
    payload = {
        "family": "data_quality",
        "metric": metric_definition(control),
        "reading": reading(control),
        "trend": points,
        "coverageNote": _coverage(points),
        "trendCaption": "Workbook pass rate from dq_results. Status is the supplied RAG.",
        "investigationAvailable": investigation_available,
        "snapshotUnavailable": control["snapshotUnavailable"],
    }
    if not control["snapshotUnavailable"]:
        payload["workbook"] = {
            "regulation": control["regulation"],
            "report": control["report"],
            "cde": control["cde"],
            "sourceSystem": control["sourceSystem"],
            "checkLogic": control["checkLogic"],
            "principle": control["principle"],
            "severity": control["severity"],
            "failed": control["failed"],
            "total": control["total"],
            "firstRed": control["firstRed"],
            "lastRed": control["lastRed"],
            "pointCount": control["pointCount"] or len(points),
            "hasDeskSplit": control["hasDeskSplit"],
        }
    return payload


def desk_breakdown(control_id: str, *, has_desk_split: bool, rows: list[dict], requested_date: str | None) -> dict:
    if not has_desk_split:
        return {
            "controlId": control_id,
            "date": requested_date,
            "available": False,
            "reason": "dq_results_by_desk does not include this control.",
            "rows": [],
        }
    if not rows:
        return {
            "controlId": control_id,
            "date": requested_date,
            "available": False,
            "reason": "No desk row for that date.",
            "rows": [],
        }
    return {
        "controlId": control_id,
        "date": rows[0].get("date") or requested_date,
        "available": True,
        "reason": "Failed-record share uses the desk rows for this control and date.",
        "rows": [{key: value for key, value in row.items() if key != "date"} for row in rows],
    }


def note_payload(events: list | None = None, commentary: list | None = None) -> dict:
    return {"events": list(events or []), "commentary": list(commentary or [])}


def _coverage(points: list[dict]) -> str:
    if not points:
        return "No dq_results rows are stored for this control. No pass rate was invented."
    return f"{len(points)} supplied dq_results points from {points[0]['date']} to {points[-1]['date']}. Dates with no row are omitted."


def established_lines(control: dict, desks: dict, notes: dict) -> list[str]:
    lines = [
        f"{control['name']} ({control['id']}) measures {control['cde']}. Check logic from the workbook: {control['checkLogic']}",
    ]
    if control["snapshotUnavailable"]:
        lines.append("No snapshot row is stored for this control. Pass rate, RAG, and counts are not invented.")
        return lines
    lines.append(
        f"Latest supplied result on {control['asOf']} is {_rate(control['passRate'])}% "
        f"({_int(control['failed'])} failed of {_int(control['total'])}), RAG {control['status']}. "
        f"Green is {_rate(control['green'])}% and amber is {_rate(control['amber'])}%."
    )
    if control["firstRed"]:
        lines.append(f"The first red row in dq_results is {control['firstRed']}.")
    else:
        lines.append("The supplied series has no red row.")
    rows = desks.get("rows") or []
    if len(rows) >= 2:
        top, second = rows[0], rows[1]
        lines.append(
            f"On {desks.get('date')}, {top['deskName']} has the most failed records "
            f"({_int(top['failed'])}, {top['shareOfFailures']}% of this control's failures). "
            f"{second['deskName']} is next at {_int(second['failed'])}. "
            "This ranking uses failure volume, not the lowest pass rate."
        )
    elif len(rows) == 1:
        top = rows[0]
        lines.append(
            f"On {desks.get('date')}, {top['deskName']} accounts for {_int(top['failed'])} failed records."
        )
    open_count = control["openExceptions"] or 0
    total = control["exceptionCount"] or 0
    oldest = control["oldestOpenAge"]
    age = f", oldest ageing {oldest} days" if open_count and oldest is not None else ""
    lines.append(f"{total} exception rows link to {control['id']} by control id. {open_count} are Open{age}.")
    if notes["events"]:
        lines.append(
            f"{len(notes['events'])} change or incident rows list related_control_id {control['id']}. "
            "That is a supplied link, not a proof that the event caused the RAG."
        )
    return lines


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _int(value: int | None) -> str:
    return f"{value or 0:,}"


def desk_names_in(text: str | None, desk_names: list[str]) -> set[str]:
    if not text:
        return set()
    haystack = text.lower()
    found: set[str] = set()
    for name in desk_names:
        tokens = [name]
        first = name.split()[0]
        if len(first) >= 8 and first.lower() != name.lower():
            tokens.append(first)
        if any(token.lower() in haystack for token in tokens):
            found.add(name)
    return found


def discrepancy_sentence(control_id: str, story_names: set[str], commentary_names: set[str]) -> str | None:
    if not story_names or not commentary_names or story_names & commentary_names:
        return None
    story = ", ".join(sorted(story_names))
    commentary = ", ".join(sorted(commentary_names))
    return (
        f"{control_id}: the planted story names {story}. "
        f"The supplied commentary names {commentary}. Both are shown and not reconciled."
    )
