import logging
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.analysis.service import cached_analysis, run_analysis
from app.core.errors import AppError, bad_request
from app.db.connection import connect, fetch_one
from app.dq import service

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
        logger.info("snowflake request failed error=%s", type(exc).__name__)
        raise AppError(502, "UPSTREAM_ERROR", "The data service could not complete the request.") from exc


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
    return _call(request, lambda connection: service.metadata(connection, _settings(request)))


@router.get("/overview")
def overview(request: Request):
    return _call(request, lambda connection: service.overview(connection, _settings(request)))


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
    return _call(
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
    )


@router.get("/controls/{control_id}")
def control_detail(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _call(request, lambda connection: service.control_detail(connection, _settings(request), control_id))


@router.get("/controls/{control_id}/trend")
def control_trend(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _call(request, lambda connection: service.control_trend(connection, _settings(request), control_id))


@router.get("/controls/{control_id}/desks")
def control_desks(request: Request, control_id: str, date: str | None = None):
    control_id = _control_id(control_id)
    if date and not _DATE.fullmatch(date):
        raise bad_request("date must be YYYY-MM-DD.")
    return _call(request, lambda connection: service.control_desks(connection, _settings(request), control_id, date))


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
    return _call(
        request,
        lambda connection: service.control_exceptions(connection, _settings(request), control_id, status, page, pageSize),
    )


@router.get("/controls/{control_id}/notes")
def control_notes(request: Request, control_id: str):
    control_id = _control_id(control_id)
    return _call(request, lambda connection: service.control_notes(connection, _settings(request), control_id))


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

    return _call(request, load)


@router.post("/controls/{control_id}/analyses")
def post_analysis(request: Request, control_id: str, body: AnalysisBody):
    control_id = _control_id(control_id)
    kind = body.analysisType.upper()
    return _call(
        request,
        lambda connection: run_analysis(connection, _settings(request), control_id, kind, body.forceRefresh),
    )
