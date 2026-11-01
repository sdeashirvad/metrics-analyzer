import logging

from app.analysis.validator import ValidationError, assert_supported, parse_narrative
from app.config import Settings
from app.core.errors import bad_request, not_found, upstream
from app.cortex.agent_client import run_agent
from app.cortex.prompts import investigation_prompt, prompt_version, summary_prompt
from app.db import analyses
from app.db.controls import get_control
from app.db.desks import desks as load_desks
from app.db.evidence import notes as load_notes
from app.db.history import history
from app.db.portfolio import desk_names
from app.dq.mapping import NOT_SUPPLIED, SUMMARY_DISCLAIMER, desk_breakdown, desk_names_in, discrepancy_sentence, established_lines

logger = logging.getLogger(__name__)


def cached_analysis(connection, settings: Settings, control_id: str, analysis_type: str) -> dict | None:
    _require_control(connection, settings, control_id)
    row = analyses.find_completed(
        connection,
        settings,
        control_id,
        analysis_type,
        prompt_version(analysis_type),
    )
    if not row:
        return None
    response = (row["result"] or {}).get("response")
    if not isinstance(response, dict):
        return None
    response = dict(response)
    response["cached"] = True
    response["generatedAt"] = row["generatedAt"]
    return response


def run_analysis(connection, settings: Settings, control_id: str, analysis_type: str, force_refresh: bool) -> dict:
    if analysis_type not in {"SUMMARY", "INVESTIGATION"}:
        raise bad_request("analysisType must be SUMMARY or INVESTIGATION.")
    control = _require_control(connection, settings, control_id)
    if control["snapshotUnavailable"]:
        raise bad_request("This control has no snapshot, so no narrative is generated.")
    version = prompt_version(analysis_type)
    if not force_refresh:
        existing = cached_analysis(connection, settings, control_id, analysis_type)
        if existing:
            return existing
    facts, context = _context(connection, settings, control)
    prompt = summary_prompt(facts) if analysis_type == "SUMMARY" else investigation_prompt(facts)
    try:
        answer = run_agent(connection, settings, prompt)
        narrative = parse_narrative(answer, analysis_type)
        assert_supported(narrative, facts, control_id)
    except TimeoutError as exc:
        _fail(connection, settings, control, analysis_type, version, "Cortex agent timed out")
        raise upstream("The analysis did not finish in time.", timeout=True) from exc
    except ValidationError as exc:
        logger.info("analysis validation failed control=%s type=%s", control_id, analysis_type)
        _fail(connection, settings, control, analysis_type, version, str(exc))
        raise upstream("The analysis could not be validated.") from exc
    except Exception as exc:
        logger.info("analysis agent failed control=%s type=%s error=%s", control_id, analysis_type, type(exc).__name__)
        message = str(exc).lower()
        _fail(connection, settings, control, analysis_type, version, type(exc).__name__)
        if "timeout" in message or "timed out" in message:
            raise upstream("The analysis did not finish in time.", timeout=True) from exc
        raise upstream("The analysis service did not return a usable narrative.") from exc
    response = _response(control, analysis_type, narrative, context)
    analyses.insert_run(
        connection,
        settings,
        control_id=control_id,
        analysis_type=analysis_type,
        control_data_version=control["controlDataVersion"],
        dataset_version=control["datasetVersion"] or 0,
        prompt_version=version,
        calculation_version=control["calculationVersion"] or settings.calculation_version,
        status="COMPLETED",
        result={"narrative": narrative, "response": response},
        error_text=None,
    )
    response = dict(response)
    response["cached"] = False
    return response


def _fail(connection, settings, control, analysis_type, version, error_text: str) -> None:
    try:
        analyses.insert_run(
            connection,
            settings,
            control_id=control["id"],
            analysis_type=analysis_type,
            control_data_version=control["controlDataVersion"],
            dataset_version=control["datasetVersion"] or 0,
            prompt_version=version,
            calculation_version=control["calculationVersion"] or settings.calculation_version,
            status="FAILED",
            result=None,
            error_text=error_text,
        )
    except Exception:
        logger.info("failed to record analysis failure control=%s", control["id"])


def _require_control(connection, settings, control_id: str) -> dict:
    control = get_control(connection, settings, control_id)
    if not control:
        raise not_found()
    return control


def _context(connection, settings, control: dict) -> tuple[dict, dict]:
    series = history(connection, settings, control["id"])
    rows = load_desks(connection, settings, control["id"], control["asOf"]) if control["hasDeskSplit"] else []
    desk_payload = desk_breakdown(
        control["id"],
        has_desk_split=control["hasDeskSplit"],
        rows=rows,
        requested_date=control["asOf"],
    )
    note_payload = load_notes(connection, settings, control["id"])
    names = desk_names(connection, settings)
    story_names = desk_names_in(control["plantedStory"], names)
    commentary_text = "\n".join(item["text"] for item in note_payload["commentary"])
    commentary_names = desk_names_in(commentary_text, names)
    discrepancy = discrepancy_sentence(control["id"], story_names, commentary_names)
    facts = {
        "controlId": control["id"],
        "name": control["name"],
        "dimension": control["dimension"],
        "frequency": control["frequency"],
        "cde": control["cde"],
        "checkLogic": control["checkLogic"],
        "owner": control["owner"],
        "thresholds": {"green": control["green"], "amber": control["amber"]},
        "plantedStory": control["plantedStory"],
        "snapshot": {
            "passRate": control["passRate"],
            "rag": control["status"],
            "failed": control["failed"],
            "total": control["total"],
            "asOf": control["asOf"],
            "firstRed": control["firstRed"],
            "lastRed": control["lastRed"],
            "recovered": control["recovered"],
            "pointCount": control["pointCount"],
            "openExceptions": control["openExceptions"],
            "exceptionCount": control["exceptionCount"],
            "oldestOpenAge": control["oldestOpenAge"],
        },
        "history": [
            {"date": row["date"], "passRate": row["passRate"], "rag": row["status"], "failed": row["failed"], "total": row["total"]}
            for row in series
        ],
        "desks": desk_payload["rows"],
        "events": note_payload["events"],
        "commentary": note_payload["commentary"],
    }
    return facts, {
        "series": series,
        "desks": desk_payload,
        "notes": note_payload,
        "discrepancy": discrepancy,
    }


def _response(control: dict, analysis_type: str, narrative: dict, context: dict) -> dict:
    if analysis_type == "SUMMARY":
        return {
            "controlId": control["id"],
            "text": narrative["text"],
            "movement": narrative["movement"],
            "thresholdPosition": narrative["thresholdPosition"],
            "implications": narrative["implications"],
            "disclaimer": SUMMARY_DISCLAIMER,
            "cached": False,
            "generatedAt": None,
        }
    hypothesis = list(narrative["hypothesis"])
    hypothesis.append(f"Implications: {narrative['implications']}")
    hypothesis.extend(f"Validation step: {step}" for step in narrative["validationSteps"])
    return {
        "kind": "data_quality",
        "metricId": control["id"],
        "name": control["name"],
        "dimension": control["dimension"],
        "readme": control["plantedStory"] or "",
        "established": established_lines(control, context["desks"], context["notes"]),
        "hypothesis": hypothesis,
        "notSupplied": [NOT_SUPPLIED],
        "discrepancy": context["discrepancy"],
        "disclaimer": SUMMARY_DISCLAIMER,
        "desks": context["desks"],
        "notes": context["notes"],
        "exceptions": {
            "total": control["exceptionCount"] or 0,
            "open": control["openExceptions"] or 0,
            "oldestAge": control["oldestOpenAge"],
        },
        "cached": False,
        "generatedAt": None,
    }
