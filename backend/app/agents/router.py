"""Agent HTTP routes. Include `router` from the application entrypoint; this module does not mount itself."""

from __future__ import annotations

import inspect
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

from app.agents.context.builder import build_preview
from app.agents.conversations import (
    create_conversation,
    export_query,
    get_context,
    get_conversation,
    get_run,
    request_fingerprint,
    retry_run,
    send_message,
)
from app.agents.faults import ApiFault
from app.agents.limits import memory
from app.agents.models import ContextRequest, CreateConversationBody, SendMessageBody
from app.agents.principal import get_principal
from app.agents.registry import public_catalog
from app.agents.tokens import signing_key
from app.common.v2_envelope import ok
from app.common.v2_errors import V2Error

logger = logging.getLogger(__name__)


def _bind(request: Request) -> None:
    if not getattr(request.state, "request_id", None):
        request.state.request_id = uuid.uuid4().hex
    get_principal()


def _route_class():
    import app.common.v2_errors as errors

    for name in ("V2APIRoute", "V2Route"):
        candidate = getattr(errors, name, None)
        if isinstance(candidate, type) and issubclass(candidate, APIRoute):
            return candidate
    return APIRoute


router = APIRouter(prefix="/api/v1/agents", route_class=_route_class(), dependencies=[Depends(_bind)])


def _settings(request: Request):
    return request.app.state.settings


def _key(request: Request) -> bytes:
    return signing_key(_settings(request).snowflake_password)


def _raise_fault(exc: ApiFault) -> None:
    raise V2Error(
        exc.code,
        exc.message,
        exc.status,
        retryable=exc.retryable,
        retry_after_ms=exc.retry_after_ms,
        details=exc.details,
    )


def _guard(fn):
    try:
        return fn()
    except ApiFault as exc:
        _raise_fault(exc)
    except V2Error:
        raise
    except Exception as exc:
        logger.info("agent request failed error=%s", type(exc).__name__)
        _raise_fault(ApiFault(502, "UPSTREAM_ERROR", "The data service could not complete the request.", retryable=True))


def _definitions_version() -> str:
    try:
        from app.portfolio.definitions import DEFINITIONS_VERSION
    except ImportError:
        return ""
    return str(DEFINITIONS_VERSION)


def _envelope(data, request: Request, *, as_of: str | None = None, warnings=None):
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    kwargs = {
        "request_id": request_id,
        "source": "snowflake",
        "definitions_version": _definitions_version(),
        "as_of": as_of,
        "cache": {"hit": False, "ageSeconds": 0, "ttlSeconds": 0},
        "warnings": list(warnings or []),
    }
    parameters = inspect.signature(ok).parameters
    if not any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values()):
        kwargs = {key: value for key, value in kwargs.items() if key in parameters}
    body = ok(data, **kwargs)
    if hasattr(body, "model_dump"):
        body = body.model_dump(mode="json")
    return body


def _json(request: Request, data, *, status_code: int = 200, as_of: str | None = None, warnings=None):
    return JSONResponse(status_code=status_code, content=_envelope(data, request, as_of=as_of, warnings=warnings))


def _idempotent(scope: str, payload: dict, client_id: str, request: Request, producer):
    fingerprint = request_fingerprint(scope, payload)
    with memory.client_lock(client_id):
        stored = memory.recall(client_id, fingerprint)
        if stored is not None:
            return JSONResponse(status_code=stored[0], content=stored[1])
        status_code, data, as_of = producer()
        body = _envelope(data, request, as_of=as_of)
        memory.remember(client_id, fingerprint, status_code, body)
        return JSONResponse(status_code=status_code, content=body)


@router.get("")
def list_agents(request: Request):
    def run():
        return _json(request, public_catalog(memory.availability()))
    return _guard(run)


@router.post("/context/preview")
def preview_context(request: Request, body: ContextRequest):
    def run():
        data = build_preview(body.model_dump())
        return _json(request, data, as_of=data["scope"]["month"], warnings=data.get("warnings"))
    return _guard(run)


@router.post("/conversations")
def post_conversation(request: Request, body: CreateConversationBody):
    payload = body.model_dump()

    def run():
        return _idempotent("create", payload, payload["clientRequestId"], request, lambda: _created(request, payload))

    return _guard(run)


@router.get("/conversations/{conversationId}")
def read_conversation(request: Request, conversationId: str):
    def run():
        data = get_conversation(_settings(request), conversationId, _key(request))
        return _json(request, data, as_of=data["conversation"]["scope"].get("month") or None)
    return _guard(run)


@router.get("/conversations/{conversationId}/context")
def read_conversation_context(request: Request, conversationId: str):
    def run():
        return _json(request, get_context(_settings(request), conversationId, _key(request)))
    return _guard(run)


@router.post("/conversations/{conversationId}/messages")
def post_message(request: Request, conversationId: str, body: SendMessageBody):
    payload = body.model_dump()

    def run():
        return _idempotent(
            conversationId,
            payload,
            payload["clientRequestId"],
            request,
            lambda: _sent(request, conversationId, payload),
        )

    return _guard(run)


@router.get("/conversations/{conversationId}/messages/{messageId}/queries/{index}/export")
def export_csv(request: Request, conversationId: str, messageId: str, index: int):
    def run():
        text, filename = export_query(_settings(request), conversationId, messageId, index, _key(request))
        return Response(
            content=text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return _guard(run)


@router.get("/runs/{runId}")
def read_run(request: Request, runId: str):
    def run():
        return _json(request, get_run(_settings(request), runId, _key(request)))
    return _guard(run)


@router.post("/runs/{runId}/retry")
def post_retry(request: Request, runId: str):
    def run():
        status_code, data = retry_run(_settings(request), runId, _key(request))
        return _json(request, data, status_code=status_code)
    return _guard(run)


def _created(request: Request, payload: dict):
    status_code, data = create_conversation(_settings(request), payload, _key(request))
    return status_code, data, data["conversation"]["scope"]["month"]


def _sent(request: Request, conversation_id: str, payload: dict):
    status_code, data = send_message(_settings(request), conversation_id, payload, _key(request))
    return status_code, data, None
