"""V2 errors and the route wrapper that turns them into the contract error body.

The legacy app keeps its own handlers. This route class is scoped to routers that opt in,
so mounting the portfolio router does not change dq or tr responses.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)


class V2Error(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        retryable: bool = False,
        details: dict | None = None,
        field_errors: list | None = None,
        retry_after_ms: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details
        self.field_errors = field_errors
        self.retry_after_ms = retry_after_ms


def not_found(code: str, message: str, details: dict | None = None) -> V2Error:
    return V2Error(code, message, 404, details=details)


def validation(
    message: str,
    *,
    code: str = "VALIDATION_FAILED",
    field: str | None = None,
    field_code: str = "INVALID",
    details: dict | None = None,
) -> V2Error:
    field_errors = None
    if field:
        field_errors = [{"field": field, "code": field_code, "message": message}]
    return V2Error(code, message, 400, details=details, field_errors=field_errors)


def conflict(code: str, message: str, details: dict | None = None) -> V2Error:
    return V2Error(code, message, 409, details=details)


def unavailable(
    message: str,
    *,
    code: str = "DATA_SOURCE_UNAVAILABLE",
    details: dict | None = None,
) -> V2Error:
    return V2Error(code, message, 503, retryable=code != "FALLBACK_UNSUPPORTED", details=details)


def upstream(message: str = "The data service could not complete the request.") -> V2Error:
    return V2Error("UPSTREAM_ERROR", message, 502, retryable=True)


def timeout(message: str = "The data service did not answer in time.") -> V2Error:
    return V2Error("UPSTREAM_TIMEOUT", message, 504, retryable=True)


def _from_request_validation(exc: RequestValidationError) -> V2Error:
    field_errors = []
    for item in exc.errors():
        loc = [str(part) for part in item.get("loc", []) if part not in {"query", "path", "body"}]
        field = ".".join(loc) or "request"
        message = str(item.get("msg") or "Invalid value.")[:200]
        field_errors.append({"field": field, "code": "INVALID", "message": message})
    return V2Error(
        "VALIDATION_FAILED",
        "The request is not valid.",
        400,
        field_errors=field_errors or None,
    )


class V2Route(APIRoute):
    """Converts V2Error and request-validation failures without touching the legacy handlers."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            request_id = uuid.uuid4().hex
            request.state.request_id = request_id
            started = time.perf_counter()
            try:
                response = await original(request)
            except V2Error as exc:
                response = JSONResponse(status_code=exc.status_code, content=_body(exc, request_id))
            except RequestValidationError as exc:
                err = _from_request_validation(exc)
                response = JSONResponse(status_code=err.status_code, content=_body(err, request_id))
            except Exception as exc:
                logger.info("portfolio unhandled error=%s", type(exc).__name__)
                err = upstream()
                response = JSONResponse(status_code=err.status_code, content=_body(err, request_id))
            logger.info(
                "portfolio route=%s status=%s duration_ms=%s source=%s cache_hit=%s request_id=%s",
                request.url.path,
                getattr(response, "status_code", None),
                int((time.perf_counter() - started) * 1000),
                getattr(request.state, "v2_source", None),
                getattr(request.state, "v2_cache_hit", None),
                request_id,
            )
            return response

        return handler


def _body(exc: V2Error, request_id: str) -> dict:
    from app.common.v2_envelope import error_body

    return error_body(exc, request_id)
