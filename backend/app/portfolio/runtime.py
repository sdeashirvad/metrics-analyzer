"""Cache, circuit and envelope for portfolio reads."""

from __future__ import annotations

import logging

from app.common.v2_envelope import DATASET_VERSION, ok
from app.common.v2_errors import V2Error, timeout, unavailable, upstream
from app.db.connection import ReadTimeout, begin_read_deadline, connect_read, dependency_failure, end_read_deadline
from app.portfolio import fallback, repository, snapshots
from app.portfolio.cache import PROBE_KEY, PROBE_TTL, catalog_key, response_cache, response_key
from app.portfolio.definitions import DEFINITIONS_VERSION
from app.portfolio.gate import portfolio_gate
from app.portfolio.month import resolve_month
from app.portfolio.scope import ensure_month, validate_scope_values

logger = logging.getLogger(__name__)


class _Dependency(Exception):
    def __init__(self, exc: BaseException) -> None:
        super().__init__(type(exc).__name__)
        self.exc = exc


def execute(
    request,
    *,
    endpoint: str,
    params: dict,
    ttl: int,
    produce,
    fallback_fn=None,
    scope=None,
    require_catalog: bool = True,
    validate_month: bool = True,
    dependency: str = "unsupported",
    lineage=None,
):
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        import uuid

        request_id = uuid.uuid4().hex
        request.state.request_id = request_id

    cached_probe = _cached_probe()
    if cached_probe is not None:
        hit = _try_hit(endpoint, params, scope, cached_probe, require_catalog, validate_month, ttl, lineage)
        if hit is not None:
            return _envelope(request, hit[0], hit[1], "snowflake", cached_probe, request_id)

    if portfolio_gate.allow() == "fallback":
        return _from_fallback(request, fallback_fn, dependency, request_id, lineage, endpoint, params, ttl)

    token = begin_read_deadline()
    settled = False
    try:
        with connect_read(_settings(request)) as connection:
            probe = cached_probe or _load_probe(connection)
            catalog = _catalog(connection, probe) if require_catalog else _cached_catalog(probe)
            if scope is not None:
                _check_scope(scope, probe, catalog, validate_month and require_catalog)
            month, source = _resolve(scope, probe)
            if scope is not None and validate_month:
                ensure_month(month, probe["months"])
            resolved = scope.with_resolved(month, source) if scope is not None else None
            key_params = dict(params)
            key_params["month"] = month
            key = response_key(endpoint, key_params, probe.get("promotedAt"))
            found = response_cache.get(key)
            if found is not None:
                payload, age, stored_ttl = found
                settled = True
                portfolio_gate.succeed()
                return _envelope(
                    request,
                    _with_lineage(payload, lineage),
                    {"hit": True, "ageSeconds": age, "ttlSeconds": stored_ttl},
                    "snowflake",
                    probe,
                    request_id,
                )
            payload = produce(connection, probe, catalog, resolved)
            if lineage and "lineage" not in payload:
                payload = {**payload, "lineage": lineage}
            response_cache.set(key, payload, ttl)
        portfolio_gate.succeed()
        settled = True
        return _envelope(
            request,
            payload,
            {"hit": False, "ageSeconds": 0, "ttlSeconds": ttl},
            "snowflake",
            probe,
            request_id,
        )
    except V2Error:
        portfolio_gate.succeed()
        settled = True
        raise
    except _Dependency:
        raise
    except Exception as exc:
        if dependency_failure(exc):
            portfolio_gate.fail()
            settled = True
            logger.info("portfolio read failed error=%s", type(exc).__name__)
            return _from_fallback(
                request,
                fallback_fn,
                dependency,
                request_id,
                lineage,
                endpoint,
                params,
                ttl,
                timeout_exc=isinstance(exc, ReadTimeout),
            )
        logger.info("portfolio query failed error=%s", type(exc).__name__)
        raise upstream() from exc
    finally:
        end_read_deadline(token)
        if not settled:
            portfolio_gate.cancel_probe()


def _try_hit(endpoint, params, scope, probe, require_catalog, validate_month, ttl, lineage):
    catalog = _cached_catalog(probe) if require_catalog else None
    if require_catalog and catalog is None:
        return None
    try:
        if scope is not None:
            _check_scope(scope, probe, catalog, validate_month and require_catalog)
        month, _source = _resolve(scope, probe)
        if scope is not None and validate_month:
            ensure_month(month, probe["months"])
    except V2Error:
        raise
    key_params = dict(params)
    key_params["month"] = month
    found = response_cache.get(response_key(endpoint, key_params, probe.get("promotedAt")))
    if found is None:
        return None
    payload, age, stored_ttl = found
    return _with_lineage(payload, lineage), {"hit": True, "ageSeconds": age, "ttlSeconds": stored_ttl}


UNSUPPORTED_MESSAGE = (
    "Snowflake is unreachable and this view is not packaged for this exact month and filter combination. "
    "Packaged data covers every month at the default scope, and each single filter value at the latest month."
)


def _from_fallback(request, fallback_fn, dependency, request_id, lineage, endpoint, params, ttl, timeout_exc=False):
    # A recorded response is the live API's own answer for this exact scope, so it wins over the
    # older promoted-extract calculation, which does not carry every field.
    recorded_first = _recorded(request, request_id, lineage)
    if recorded_first is not None:
        return recorded_first
    found = response_cache.get(response_key(endpoint, params, "packaged"))
    if found is not None and fallback_fn is not None:
        payload, age, stored_ttl = found
        meta = fallback.dataset_meta() if fallback.available() else {
            "version": DATASET_VERSION,
            "rowCount": 0,
            "promotedAt": None,
        }
        probe = {"version": meta["version"], "rowCount": meta["rowCount"], "promotedAt": meta["promotedAt"]}
        return _envelope(
            request,
            _with_lineage(payload, lineage),
            {"hit": True, "ageSeconds": age, "ttlSeconds": stored_ttl},
            "packaged",
            probe,
            request_id,
        )
    if fallback_fn is None:
        recorded = _recorded(request, request_id, lineage)
        if recorded is not None:
            return recorded
        if timeout_exc:
            raise timeout()
        if dependency == "unavailable":
            raise unavailable("Snowflake did not answer.")
        raise unavailable(UNSUPPORTED_MESSAGE, code="FALLBACK_UNSUPPORTED")
    try:
        payload = fallback_fn()
    except V2Error as exc:
        if exc.code == "FALLBACK_UNSUPPORTED":
            recorded = _recorded(request, request_id, lineage)
            if recorded is not None:
                return recorded
            raise unavailable(UNSUPPORTED_MESSAGE, code="FALLBACK_UNSUPPORTED") from exc
        raise
    if lineage and payload.get("lineage") is None:
        payload = {**payload, "lineage": lineage}
    promoted = "packaged"
    key = response_key(endpoint, params, promoted)
    response_cache.set(key, payload, ttl)
    meta = fallback.dataset_meta() if fallback.available() else {
        "version": DATASET_VERSION,
        "rowCount": 0,
        "promotedAt": None,
    }
    probe = {"version": meta["version"], "rowCount": meta["rowCount"], "promotedAt": meta["promotedAt"]}
    return _envelope(
        request,
        payload,
        {"hit": False, "ageSeconds": 0, "ttlSeconds": ttl},
        "packaged",
        probe,
        request_id,
    )


def _recorded(request, request_id, lineage):
    payload = snapshots.lookup(request)
    if payload is None:
        return None
    meta = fallback.dataset_meta() if fallback.available() else {
        "version": DATASET_VERSION,
        "rowCount": 0,
        "promotedAt": None,
    }
    probe = {"version": meta["version"], "rowCount": meta["rowCount"], "promotedAt": meta["promotedAt"]}
    return _envelope(
        request,
        _with_lineage(payload, lineage),
        {"hit": False, "ageSeconds": 0, "ttlSeconds": 0},
        "packaged",
        probe,
        request_id,
    )


def _envelope(request, payload, cache_meta, source, probe, request_id):
    request.state.v2_source = source
    request.state.v2_cache_hit = cache_meta["hit"]
    dataset = {
        "version": (probe or {}).get("version") or DATASET_VERSION,
        "rowCount": int((probe or {}).get("rowCount") or 0),
        "promotedAt": None if probe is None else probe.get("promotedAt"),
    }
    return ok(
        payload["data"],
        request_id=request_id,
        source=source,
        definitions_version=DEFINITIONS_VERSION,
        dataset=dataset,
        cache=cache_meta,
        as_of=payload.get("asOf"),
        warnings=payload.get("warnings") or [],
        lineage=payload.get("lineage"),
    )


def _check_scope(scope, probe, catalog, validate_values: bool) -> None:
    if catalog is not None and validate_values:
        validate_scope_values(scope, catalog)
    elif catalog is not None and scope.month:
        ensure_month(scope.month, probe["months"])


def _resolve(scope, probe):
    explicit = None if scope is None else scope.month
    if not probe.get("latestMonth"):
        raise unavailable("No reporting month is available.")
    return resolve_month(explicit, known_latest=probe["latestMonth"])


def _cached_probe():
    found = response_cache.get(PROBE_KEY)
    if found is None:
        return None
    return found[0]


def _cached_catalog(probe):
    if probe is None:
        return None
    found = response_cache.get(catalog_key(probe.get("promotedAt")))
    if found is None:
        return None
    return found[0]


def _load_probe(connection) -> dict:
    cached = _cached_probe()
    if cached is not None:
        return cached
    loaded = repository.probe(connection)
    response_cache.set(PROBE_KEY, loaded, PROBE_TTL)
    return loaded


def _catalog(connection, probe) -> dict:
    cached = _cached_catalog(probe)
    if cached is not None:
        return cached
    if not probe.get("latestMonth"):
        raise unavailable("No reporting month is available.")
    loaded = repository.catalog(connection, probe["latestMonth"])
    response_cache.set(catalog_key(probe.get("promotedAt")), loaded, PROBE_TTL)
    return loaded


def _with_lineage(payload, lineage):
    if lineage and not payload.get("lineage"):
        return {**payload, "lineage": lineage}
    return payload


def _settings(request):
    return request.app.state.settings
