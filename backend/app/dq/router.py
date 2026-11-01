import logging
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.analysis.service import (
    active_investigation,
    begin_investigation,
    begin_summary,
    cached_analysis,
    investigation_preview,
    operation_status,
)
from app.core.errors import AppError, bad_request
from app.db.connection import begin_read_deadline, connect, connect_read, dependency_failure, end_read_deadline, fetch_one
from app.dq import service
from app.fallback import catalog
from app.fallback.gates import snowflake_gate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dq")
_CONTROL_ID = re.compile(r"^DQ-\d{3}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AnalysisBody(BaseModel):
    analysisType: str
    forceRefresh: bool = False


def _settings(request: Request):
    return request.app.state.settings


def _control_id(control_id: str) -> str:
    if not _CONTROL_ID.fullmatch(control_id):
        raise bad_request("Control id must look like DQ-001.")
    return control_id


def _call(request: Request, fn):
    try:
        with connect(_settings(request)) as connection:
            return fn(connection)
    except AppError:
        raise
    except Exception as exc:
        if dependency_failure(exc):
            raise
        logger.info("snowflake request failed error=%s", type(exc).__name__)
        raise AppError(502, "UPSTREAM_ERROR", "The data service could not complete the request.") from exc


def _read(request: Request, fn, fallback):
    if snowflake_gate.allow() == "fallback":
        return fallback()
    token = begin_read_deadline()
    settled = False
    try:
        with connect_read(_settings(request)) as connection:
            result = fn(connection)
        snowflake_gate.succeed()
        settled = True
        return result
    except AppError:
        snowflake_gate.succeed()
        settled = True
        raise
    except Exception as exc:
        if dependency_failure(exc):
            snowflake_gate.fail()
            settled = True
            logger.info("dq read used packaged data error=%s", type(exc).__name__)
            return fallback()
        raise
    finally:
        if not settled:
            snowflake_gate.cancel_probe()
        end_read_deadline(token)


def _packaged_analysis(control_id: str, kind: str):
    if kind == "SUMMARY":
        return catalog.summary_for(control_id)
    return catalog.investigation_for(control_id)


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request):
    try:
        with connect(_settings(request)) as connection:
            fetch_one(connection, "SELECT 1 AS OK")
    except Exception:
        logger.info("ready check failed")
        return JSONResponse(status_code=503, content={"code": "NOT_READY", "message": "Snowflake is not reachable."})
    return {"status": "ok"}


@router.get("/metadata")
def metadata(request: Request):
    return _read(request, lambda connection: service.metadata(connection, _settings(request)), catalog.metadata)


@router.get("/overview")
def overview(request: Request):
    return _read(request, lambda connection: service.overview(connection, _settings(request)), catalog.overview)


@router.get("/controls")
def controls(
    request: Request,
    q: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    investigation: bool | None = None,
    page: int = Query(1),
    pageSize: int = Query(25),
):
    service.parse_page(page, pageSize)
    return _read(
        request,
        lambda connection: service.control_list(
            connection,
            _settings(request),
            q=q,
            domain=domain,
            status=status,
            frequency=frequency,
            investigation=investigation,
            page=page,
            page_size=pageSize,
        ),
        lambda: catalog.control_list(
            q=q,
            domain=domain,
            status=status,
            frequency=frequency,
            investigation=investigation,
            page=page,
            page_size=pageSize,
        ),
    )


@router.get("/controls/{control_id}")
def control_detail(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _read(
        request,
        lambda connection: service.control_detail(connection, _settings(request), control_id),
        lambda: catalog.control_detail(control_id),
    )


@router.get("/controls/{control_id}/trend")
def control_trend(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _read(
        request,
        lambda connection: service.control_trend(connection, _settings(request), control_id),
        lambda: catalog.control_trend(control_id),
    )


@router.get("/controls/{control_id}/desks")
def control_desks(request: Request, control_id: str, date: str | None = None):
    control_id = _control_id(control_id)
    if date and not _DATE.fullmatch(date):
        raise bad_request("date must be YYYY-MM-DD.")
    return _read(
        request,
        lambda connection: service.control_desks(connection, _settings(request), control_id, date),
        lambda: catalog.control_desks(control_id, date),
    )


@router.get("/controls/{control_id}/exceptions")
def control_exceptions(
    request: Request,
    control_id: str,
    status: str | None = None,
    page: int = Query(1),
    pageSize: int = Query(25),
):
    control_id = _control_id(control_id)
    service.parse_page(page, pageSize)
    if status and len(status) > 32:
        raise bad_request("status is too long.")
    return _read(
        request,
        lambda connection: service.control_exceptions(connection, _settings(request), control_id, status, page, pageSize),
        lambda: catalog.control_exceptions(control_id, status, page, pageSize),
    )


@router.get("/controls/{control_id}/notes")
def control_notes(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _read(
        request,
        lambda connection: service.control_notes(connection, _settings(request), control_id),
        lambda: catalog.control_notes(control_id),
    )


@router.get("/controls/{control_id}/analyses/active")
def active_analysis(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _read(
        request,
        lambda connection: active_investigation(connection, _settings(request), control_id),
        lambda: {"status": "IDLE", "controlId": control_id, "analysisType": "INVESTIGATION", "cached": False},
    )


@router.get("/controls/{control_id}/analyses/preview")
def analysis_preview(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _read(
        request,
        lambda connection: investigation_preview(connection, _settings(request), control_id),
        lambda: catalog.investigation_for(control_id),
    )


@router.get("/controls/{control_id}/analyses/operations/{run_id}")
def analysis_operation(request: Request, control_id: str, run_id: str):
    control_id = _control_id(control_id)
    if len(run_id) > 36:
        raise bad_request("Run id is too long.")
    return _call(
        request,
        lambda connection: operation_status(connection, _settings(request), control_id, run_id),
    )


@router.get("/controls/{control_id}/analyses/{analysis_type}")
def get_analysis(request: Request, control_id: str, analysis_type: str):
    control_id = _control_id(control_id)
    kind = analysis_type.upper()
    if kind not in {"SUMMARY", "INVESTIGATION"}:
        raise bad_request("analysis type must be summary or investigation.")

    def load(connection):
        found = cached_analysis(connection, _settings(request), control_id, kind)
        if not found:
            raise AppError(404, "NOT_FOUND", "No cached analysis is stored for this control.")
        return found

    if kind == "SUMMARY":
        return _read(request, load, lambda: catalog.summary_for(control_id))
    return _call(request, load)


@router.post("/controls/{control_id}/analyses")
def post_analysis(request: Request, control_id: str, body: AnalysisBody):
    control_id = _control_id(control_id)
    kind = body.analysisType.upper()
    if kind not in {"SUMMARY", "INVESTIGATION"}:
        raise bad_request("analysisType must be SUMMARY or INVESTIGATION.")
    if snowflake_gate.serving_fallback():
        return _packaged_analysis(control_id, kind)
    starter = begin_investigation if kind == "INVESTIGATION" else begin_summary
    try:
        payload, code = _call(
            request,
            lambda connection: starter(connection, _settings(request), control_id, body.forceRefresh),
        )
    except Exception as exc:
        if not dependency_failure(exc):
            raise
        snowflake_gate.fail()
        logger.info("analysis start used packaged data error=%s", type(exc).__name__)
        return _packaged_analysis(control_id, kind)
    return JSONResponse(status_code=code, content=payload)
