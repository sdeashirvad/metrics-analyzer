import logging
from datetime import datetime, timezone

from app.analysis import jobs
from app.analysis.validator import ValidationError, assert_supported, parse_narrative
from app.config import Settings
from app.core.errors import AppError, bad_request, not_found, upstream
from app.cortex.agent_client import run_agent
from app.cortex.prompts import investigation_prompt, prompt_version, summary_prompt
from app.db import analyses
from app.db.connection import connect
from app.db.controls import get_control
from app.db.desks import desks as load_desks
from app.db.evidence import notes as load_notes
from app.db.history import history
from app.db.portfolio import desk_names
from app.dq.mapping import NOT_SUPPLIED, SUMMARY_DISCLAIMER, desk_breakdown, desk_names_in, discrepancy_sentence, established_lines
from app.fallback.facts import deterministic_investigation, deterministic_summary
from app.fallback.gates import cortex_gate

logger = logging.getLogger(__name__)
_STALE_SECONDS = 16 * 60
_ORPHAN_SECONDS = 20
_FAILED_MESSAGE = "The investigation did not finish. Run it again to start a new one."
_BUSY_MESSAGE = "Two investigations are already running. Wait for one to finish, then run this again."


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
    response["source"] = response.get("source") or "cortex"
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
    return _execute(connection, settings, control, analysis_type, version)


def begin_investigation(connection, settings: Settings, control_id: str, force_refresh: bool) -> tuple[dict, int]:
    control = _require_control(connection, settings, control_id)
    if control["snapshotUnavailable"]:
        raise bad_request("This control has no snapshot, so no narrative is generated.")
    version = prompt_version("INVESTIGATION")
    if not force_refresh:
        existing = cached_analysis(connection, settings, control_id, "INVESTIGATION")
        if existing:
            return existing, 200
    key = _operation_key(settings, control, version)
    with jobs.lock(key):
        if not force_refresh:
            active = analyses.find_open_running(
                connection,
                settings,
                control_id,
                "INVESTIGATION",
                version,
                control["calculationVersion"] or settings.calculation_version,
                settings.model_identity,
                control["controlDataVersion"],
            )
            if active and jobs.is_active(active["runId"]):
                return _running_payload(control_id, active["runId"], "INVESTIGATION"), 202
        decision = cortex_gate.allow()
        if decision == "fallback":
            return _investigation_preview(connection, settings, control), 200
        if not jobs.reserve():
            if decision == "probe":
                cortex_gate.cancel_probe()
            raise AppError(429, "AGENT_BUSY", _BUSY_MESSAGE)
        try:
            run_id = analyses.insert_run(
                connection,
                settings,
                control_id=control_id,
                analysis_type="INVESTIGATION",
                control_data_version=control["controlDataVersion"],
                dataset_version=control["datasetVersion"] or 0,
                prompt_version=version,
                calculation_version=control["calculationVersion"] or settings.calculation_version,
                status="RUNNING",
                result=None,
                error_text=None,
            )
        except Exception:
            jobs.cancel_reservation()
            if decision == "probe":
                cortex_gate.cancel_probe()
            raise
        jobs.activate(run_id, lambda: _worker(settings, control_id, "INVESTIGATION", version, run_id))
        return _running_payload(control_id, run_id, "INVESTIGATION"), 202


def begin_summary(connection, settings: Settings, control_id: str, force_refresh: bool) -> tuple[dict, int]:
    control = _require_control(connection, settings, control_id)
    if control["snapshotUnavailable"]:
        raise bad_request("This control has no snapshot, so no narrative is generated.")
    version = prompt_version("SUMMARY")
    if not force_refresh:
        existing = cached_analysis(connection, settings, control_id, "SUMMARY")
        if existing:
            return existing, 200
    key = _operation_key(settings, control, version)
    with jobs.lock(key):
        if not force_refresh:
            active = analyses.find_open_running(
                connection,
                settings,
                control_id,
                "SUMMARY",
                version,
                control["calculationVersion"] or settings.calculation_version,
                settings.model_identity,
                control["controlDataVersion"],
            )
            if active and jobs.is_active(active["runId"]):
                return _running_payload(control_id, active["runId"], "SUMMARY"), 202
        decision = cortex_gate.allow()
        if decision == "fallback":
            return deterministic_summary(control), 200
        if not jobs.reserve():
            if decision == "probe":
                cortex_gate.cancel_probe()
            raise AppError(429, "AGENT_BUSY", _BUSY_MESSAGE)
        try:
            run_id = analyses.insert_run(
                connection,
                settings,
                control_id=control_id,
                analysis_type="SUMMARY",
                control_data_version=control["controlDataVersion"],
                dataset_version=control["datasetVersion"] or 0,
                prompt_version=version,
                calculation_version=control["calculationVersion"] or settings.calculation_version,
                status="RUNNING",
                result=None,
                error_text=None,
            )
        except Exception:
            jobs.cancel_reservation()
            if decision == "probe":
                cortex_gate.cancel_probe()
            raise
        jobs.activate(run_id, lambda: _worker(settings, control_id, "SUMMARY", version, run_id))
        return _running_payload(control_id, run_id, "SUMMARY"), 202


def investigation_preview(connection, settings: Settings, control_id: str) -> dict:
    control = _require_control(connection, settings, control_id)
    return _investigation_preview(connection, settings, control)


def _investigation_preview(connection, settings: Settings, control: dict) -> dict:
    latest = analyses.find_latest_completed(connection, settings, control["id"], "INVESTIGATION")
    response = (latest or {}).get("result") if isinstance((latest or {}).get("result"), dict) else None
    body = response.get("response") if isinstance(response, dict) else None
    if isinstance(body, dict):
        payload = dict(body)
        payload["cached"] = True
        payload["generatedAt"] = latest["generatedAt"]
        payload["source"] = "previous_cortex"
        payload["stale"] = latest.get("controlDataVersion") != control.get("controlDataVersion")
        return payload
    _facts, context = _context(connection, settings, control)
    return deterministic_investigation(control, context["desks"], context["notes"])


def active_investigation(connection, settings: Settings, control_id: str) -> dict:
    control = _require_control(connection, settings, control_id)
    version = prompt_version("INVESTIGATION")
    active = analyses.find_open_running(
        connection,
        settings,
        control_id,
        "INVESTIGATION",
        version,
        control["calculationVersion"] or settings.calculation_version,
        settings.model_identity,
        control["controlDataVersion"],
    )
    if active and jobs.is_active(active["runId"]):
        return _running_payload(control_id, active["runId"], "INVESTIGATION")
    return {"status": "IDLE", "controlId": control_id, "analysisType": "INVESTIGATION", "cached": False}


def operation_status(connection, settings: Settings, control_id: str, run_id: str) -> dict:
    row = analyses.find_by_id(connection, settings, control_id, run_id)
    if not row or row["analysisType"] not in {"INVESTIGATION", "SUMMARY"}:
        raise not_found("That analysis run was not found.")
    kind = row["analysisType"]
    if row["status"] == "COMPLETED":
        return _completed_payload(control_id, run_id, row, kind)
    if row["status"] == "FAILED":
        return _failed_payload(control_id, run_id, row, kind)
    terminal = analyses.find_terminal_for(connection, settings, run_id)
    if terminal and terminal["status"] == "COMPLETED":
        return _completed_payload(control_id, run_id, terminal, kind)
    if terminal and terminal["status"] == "FAILED":
        return _failed_payload(control_id, run_id, terminal, kind)
    if jobs.is_active(run_id) or _age_seconds(row) < _ORPHAN_SECONDS:
        return _running_payload(control_id, run_id, kind)
    if jobs.claim_orphan(run_id):
        control = _require_control(connection, settings, control_id)
        _fail(
            connection,
            settings,
            control,
            kind,
            row["promptVersion"],
            "Investigation worker stopped" if kind == "INVESTIGATION" else "Summary worker stopped",
            operation_id=run_id,
        )
    return _failed_payload(control_id, run_id, None, kind)


def _execute(connection, settings: Settings, control: dict, analysis_type: str, version: str, operation_id: str | None = None) -> dict:
    facts, context = _context(connection, settings, control)
    prompt = summary_prompt(facts) if analysis_type == "SUMMARY" else investigation_prompt(facts)
    try:
        answer = run_agent(connection, settings, prompt)
        narrative = parse_narrative(answer, analysis_type)
        assert_supported(narrative, facts, control["id"])
    except TimeoutError as exc:
        _fail(connection, settings, control, analysis_type, version, "Cortex agent timed out", operation_id)
        raise upstream("The analysis did not finish in time.", timeout=True) from exc
    except ValidationError as exc:
        logger.info("analysis validation failed control=%s type=%s", control["id"], analysis_type)
        _fail(connection, settings, control, analysis_type, version, "ValidationError", operation_id)
        raise upstream("The analysis could not be validated.") from exc
    except Exception as exc:
        logger.info("analysis agent failed control=%s type=%s error=%s", control["id"], analysis_type, type(exc).__name__)
        message = str(exc).lower()
        _fail(connection, settings, control, analysis_type, version, type(exc).__name__, operation_id)
        if "timeout" in message or "timed out" in message:
            raise upstream("The analysis did not finish in time.", timeout=True) from exc
        raise upstream("The analysis service did not return a usable narrative.") from exc
    response = _response(control, analysis_type, narrative, context)
    stored = {"narrative": narrative, "response": response}
    if operation_id:
        stored["operationId"] = operation_id
    analyses.insert_run(
        connection,
        settings,
        control_id=control["id"],
        analysis_type=analysis_type,
        control_data_version=control["controlDataVersion"],
        dataset_version=control["datasetVersion"] or 0,
        prompt_version=version,
        calculation_version=control["calculationVersion"] or settings.calculation_version,
        status="COMPLETED",
        result=stored,
        error_text=None,
    )
    response = dict(response)
    response["cached"] = False
    return response


def _worker(settings: Settings, control_id: str, analysis_type: str, version: str, operation_id: str) -> None:
    try:
        with connect(settings) as connection:
            control = _require_control(connection, settings, control_id)
            _execute(connection, settings, control, analysis_type, version, operation_id)
        cortex_gate.succeed()
    except AppError as exc:
        if "validated" in exc.message:
            cortex_gate.succeed()
        else:
            cortex_gate.fail()
        logger.info("analysis worker ended control=%s error=%s", control_id, type(exc).__name__)
    except Exception as exc:
        cortex_gate.fail()
        logger.info("analysis worker ended control=%s error=%s", control_id, type(exc).__name__)
        try:
            with connect(settings) as connection:
                control = get_control(connection, settings, control_id)
                if control:
                    _fail(connection, settings, control, analysis_type, version, type(exc).__name__, operation_id)
        except Exception:
            logger.info("analysis failure was not recorded control=%s", control_id)


def _operation_key(settings: Settings, control: dict, version: str) -> str:
    return "|".join(
        (
            control["id"],
            "INVESTIGATION",
            version,
            control["calculationVersion"] or settings.calculation_version,
            settings.model_identity,
            str(control["controlDataVersion"]),
        )
    )


def _reusable(row: dict) -> bool:
    return jobs.is_active(row["runId"])


def _age_seconds(row: dict) -> float:
    generated = row.get("generatedAtValue")
    if not isinstance(generated, datetime):
        return _STALE_SECONDS
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - generated).total_seconds()


def _running_payload(control_id: str, run_id: str, analysis_type: str = "INVESTIGATION") -> dict:
    return {
        "status": "RUNNING",
        "runId": run_id,
        "controlId": control_id,
        "analysisType": analysis_type,
        "cached": False,
    }


def _completed_payload(control_id: str, run_id: str, row: dict, analysis_type: str = "INVESTIGATION") -> dict:
    response = ((row.get("result") or {}).get("response")) if isinstance(row.get("result"), dict) else None
    if not isinstance(response, dict):
        return _failed_payload(control_id, run_id, None, analysis_type)
    payload = dict(response)
    payload["cached"] = False
    payload["source"] = payload.get("source") or "cortex"
    return {
        "status": "COMPLETED",
        "runId": run_id,
        "controlId": control_id,
        "analysisType": analysis_type,
        "cached": False,
        "result": payload,
    }


def _failed_payload(control_id: str, run_id: str, row: dict | None, analysis_type: str = "INVESTIGATION") -> dict:
    text = (row or {}).get("errorText") or ""
    message = "The investigation took too long. Run it again." if "timed out" in text.lower() else _FAILED_MESSAGE
    return {
        "status": "FAILED",
        "runId": run_id,
        "controlId": control_id,
        "analysisType": analysis_type,
        "cached": False,
        "message": message,
        "result": None,
    }


def _fail(connection, settings, control, analysis_type, version, error_text: str, operation_id: str | None = None) -> None:
    if operation_id:
        error_text = f"op:{operation_id} {error_text}"
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
            "source": "cortex",
            "cached": False,
            "generatedAt": None,
        }
    hypothesis = list(narrative["hypothesis"])
    hypothesis.append(f"Implications: {narrative['implications']}")
    hypothesis.extend(f"Validation step: {step}" for step in narrative["validationSteps"])
    established = established_lines(control, context["desks"], context["notes"])
    return {
        "kind": "data_quality",
        "metricId": control["id"],
        "name": control["name"],
        "dimension": control["dimension"],
        "readme": control["plantedStory"] or "",
        "summary": established[0],
        "whatChanged": established[1] if len(established) > 1 else established[0],
        "whyItMatters": narrative["implications"],
        "hypotheses": list(narrative["hypothesis"]),
        "validationSteps": list(narrative["validationSteps"]),
        "established": established,
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
        "source": "cortex",
        "cached": False,
        "generatedAt": None,
    }
