"""Success and error envelopes for Metrics Analyzer V2."""

from __future__ import annotations

from datetime import datetime, timezone

from app.common.v2_errors import V2Error

CONTRACT_VERSION = "2.0.0"
DATASET_VERSION = "v1-seed20261103"


def ok(
    data,
    *,
    request_id,
    source,
    definitions_version,
    dataset=None,
    cache=None,
    as_of=None,
    warnings=None,
    lineage=None,
) -> dict:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "contractVersion": CONTRACT_VERSION,
        "definitionsVersion": definitions_version,
        "requestId": request_id,
        "generatedAt": generated,
        "asOf": as_of,
        "dataset": dataset
        or {"version": DATASET_VERSION, "rowCount": 0, "promotedAt": None},
        "source": source,
        "cache": cache or {"hit": False, "ageSeconds": 0, "ttlSeconds": 600},
        "warnings": list(warnings or []),
    }
    if lineage:
        meta["lineage"] = lineage
    return {"data": data, "meta": meta}


def error_body(exc: V2Error, request_id) -> dict:
    error = {
        "code": exc.code,
        "message": exc.message,
        "retryable": bool(exc.retryable),
        "requestId": request_id,
    }
    if exc.retry_after_ms is not None:
        error["retryAfterMs"] = exc.retry_after_ms
    if exc.field_errors:
        error["fieldErrors"] = exc.field_errors
    if exc.details:
        error["details"] = exc.details
    return {"error": error}
