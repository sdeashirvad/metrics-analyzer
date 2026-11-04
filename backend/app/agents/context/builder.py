"""Stateless context preview. Portfolio services are used when they can be imported."""

from __future__ import annotations

import calendar
import importlib
import logging
import re

from app.agents.context.catalogue import (
    APPLICATION_SURFACES,
    DEFINITION_IDS,
    METRIC_SURFACES,
    SURFACE_LABELS,
    for_surface,
)
from app.agents.context.render import PREAMBLE, clip, context_hash, month_chip, sanitize
from app.agents.faults import ApiFault
from app.agents.registry import MAX_CONTEXT_CHARS

logger = logging.getLogger(__name__)

_MONTH = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_METRIC = re.compile(r"^M[0-9]{6}$")
_EON = re.compile(r"^EON[0-9]{6}$")
_GROUND_RULES = [
    "Applications are counted once.",
    "Findings are not summed across metric rows.",
    "Organisation trees are kept separate.",
    "Tier and risk codes have no direction.",
    "Rates are provisional and are not client-confirmed.",
    "Causes are hypotheses until validated.",
    "The supplied reporting month is authoritative.",
]
_GAP = "Figures for this item were not available from the portfolio service."


def build_preview(request: dict) -> dict:
    _reject_unknown(request, {"entrySurface", "scope", "items"}, "The request is not valid.")
    surface = request.get("entrySurface")
    if surface not in SURFACE_LABELS:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    scope_in = request.get("scope") or {}
    if not isinstance(scope_in, dict):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    _reject_unknown(scope_in, {"month", "metricId", "eonId", "filters"}, "The request is not valid.")
    items_in = request.get("items") or {}
    if items_in is None:
        items_in = {}
    if not isinstance(items_in, dict):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    _reject_unknown(items_in, {"include", "exclude"}, "The request is not valid.")
    month, month_source = _resolve_month(scope_in.get("month") or (scope_in.get("filters") or {}).get("month"))
    metric_id = scope_in.get("metricId")
    eon_id = scope_in.get("eonId")
    _check_targets(surface, metric_id, eon_id)
    filters = _filters(scope_in.get("filters"), month)
    selected = _select(surface, items_in.get("include"), items_in.get("exclude"))
    version, getter = _registry()
    promoted = _promoted_at()
    portfolio = _load_portfolio(surface, selected, month, metric_id, eon_id, filters)
    built = [
        _build_item(spec, selected, surface, month, month_source, metric_id, eon_id, filters, version, getter, portfolio)
        for spec in for_surface(surface)
    ]
    rendered = _render(built)
    if len(rendered) > MAX_CONTEXT_CHARS:
        optional = [item["key"] for item in built if item["included"] and not item["required"]]
        optional.sort(key=lambda key: next(item["approxChars"] for item in built if item["key"] == key), reverse=True)
        raise ApiFault(
            400,
            "CONTEXT_TOO_LARGE",
            "The context is too large.",
            details={"largestItems": optional[:8]},
        )
    scope = {
        "eonId": eon_id,
        "filters": filters,
        "metricId": metric_id,
        "month": month,
        "monthSource": month_source,
    }
    included = [item["key"] for item in built if item["included"]]
    digest = context_hash(
        definitions_version=version,
        promoted_at=promoted,
        scope=scope,
        item_keys=included,
        rendered_text=rendered,
    )
    warnings = []
    if any(item.get("gap") for item in built if item["included"]):
        warnings.append(
            {
                "code": "PORTFOLIO_CONTEXT_UNAVAILABLE",
                "message": "Some portfolio figures were not available for this preview.",
            }
        )
    chips = _chips(metric_id, eon_id, month, month_source, portfolio)
    return {
        "contextHash": digest,
        "definitionsVersion": version,
        "entrySurface": surface,
        "scope": {
            "month": month,
            "monthSource": month_source,
            "metricId": metric_id,
            "eonId": eon_id,
            "filters": filters,
        },
        "chips": chips,
        "items": [{key: value for key, value in item.items() if key != "gap"} for item in built],
        "rendered": {"text": rendered, "chars": len(rendered), "approxTokens": max(1, round(len(rendered) / 4)) if rendered else 0},
        "warnings": warnings,
    }


def _build_item(spec, selected, surface, month, month_source, metric_id, eon_id, filters, version, getter, portfolio):
    included = spec.key in selected
    lines, definition_ids, gap = _lines(
        spec.key, included, surface, month, month_source, metric_id, eon_id, filters, version, getter, portfolio
    )
    if not included:
        lines = []
        gap = False
    summary = lines[0] if lines else spec.label
    return {
        "key": spec.key,
        "label": spec.label,
        "kind": spec.kind,
        "required": spec.required,
        "included": included,
        "defaultIncluded": spec.default_included,
        "sensitive": spec.sensitive,
        "summary": clip(summary, 180),
        "lines": lines[:12],
        "approxChars": sum(len(line) for line in lines[:12]),
        "definitionIds": definition_ids,
        "gap": gap,
    }


def _lines(key, included, surface, month, month_source, metric_id, eon_id, filters, version, getter, portfolio):
    if key == "ground_rules":
        return list(_GROUND_RULES), [], False
    if key == "definitions":
        ids = DEFINITION_IDS.get(surface, [])
        lines = ["These definitions are provisional and are not client-confirmed."]
        lines.extend(_definition_line(getter, definition_id) for definition_id in ids[:11])
        if not getter:
            lines.append("Definition registry is not loaded.")
        return lines[:12], ids, getter is None
    if key == "scope":
        source = "selected" if month_source == "selected" else "latest available"
        lines = [
            f"Entry surface: {SURFACE_LABELS.get(surface, surface)}.",
            f"Reporting month: {month} ({source}).",
        ]
        if metric_id:
            lines.append(f"Metric: {sanitize(metric_id)}.")
        if eon_id:
            lines.append(f"Application: {sanitize(eon_id)}.")
        return lines, [], False
    if key == "filters":
        return _filter_lines(filters), [], False
    if key == "metric_definition":
        lines = [_definition_line(getter, "PD-01"), _definition_line(getter, "PD-02")]
        scope = _nested(portfolio.get("metric"), "definition", "denominatorScope")
        if isinstance(scope, str):
            lines.append(f"Inferred denominator scope: {sanitize(scope, 40)}.")
        else:
            lines.append("Denominator scope is inferred from Pending rows (PD-02).")
        return lines, ["PD-01", "PD-02"], False
    readers = {
        "portfolio_kpis": lambda: _kpis(portfolio.get("overview")),
        "portfolio_trend": lambda: _series(portfolio.get("trends"), "points"),
        "org_contribution": lambda: _named_counts(portfolio.get("org"), "items", "nonCompliantApplications"),
        "attention_summary": lambda: _attention(portfolio.get("overview")),
        "data_coverage": lambda: _coverage(portfolio.get("coverage")),
        "metric_kpis": lambda: _metric_kpis(portfolio.get("metric")),
        "metric_trend": lambda: _series(portfolio.get("metric_trend"), "points"),
        "metric_org_breakdown": lambda: _named_counts(portfolio.get("metric_breakdown"), "items", "nonCompliantApplications"),
        "metric_applications": lambda: _applications(portfolio.get("metric_applications")),
        "application_attributes": lambda: _attributes(portfolio.get("application")),
        "application_status": lambda: _application_status(portfolio.get("application")),
        "application_history": lambda: _history(portfolio.get("history")),
        "application_peers": lambda: _peers(portfolio.get("application")),
        "owner_names": lambda: _owners(portfolio.get("application")),
    }
    produced = readers.get(key, lambda: None)()
    if produced:
        return produced, _ids_for(key), False
    return [_GAP], _ids_for(key), True


def _render(items: list[dict]) -> str:
    parts = [PREAMBLE]
    for item in items:
        if not item["included"]:
            continue
        parts.append(item["label"])
        parts.extend(item["lines"][:12])
    return "\n".join(parts)


def _select(surface: str, include, exclude) -> set[str]:
    specs = for_surface(surface)
    known = {spec.key for spec in specs}
    include = list(include or [])
    exclude = list(exclude or [])
    if not all(isinstance(key, str) for key in include + exclude):
        raise ApiFault(400, "CONTEXT_INVALID", "The context item is not valid.")
    for key in include + exclude:
        if key not in known:
            raise ApiFault(400, "CONTEXT_INVALID", "The context item is not available on this surface.", details={"item": key})
    required = {spec.key for spec in specs if spec.required}
    for key in exclude:
        if key in required:
            raise ApiFault(400, "CONTEXT_INVALID", "A required context item cannot be removed.", details={"item": key})
    selected = {spec.key for spec in specs if spec.required or spec.default_included}
    selected.update(include)
    selected.difference_update(exclude)
    return selected


def _resolve_month(requested) -> tuple[str, str]:
    if requested is not None:
        if not isinstance(requested, str) or not _month_end(requested):
            raise ApiFault(400, "UNKNOWN_MONTH", "The reporting month is not a known month-end.")
        _known_month(requested)
        return requested, "selected"
    from app.portfolio.gate import portfolio_gate

    # Fail fast while the portfolio circuit is open instead of waiting for another Snowflake timeout.
    latest = None if portfolio_gate.serving_fallback() else _latest_month()
    if not latest:
        raise ApiFault(503, "DATA_SOURCE_UNAVAILABLE", "The reporting month could not be resolved.", retryable=True)
    return latest, "latest_available"


def _check_targets(surface: str, metric_id, eon_id) -> None:
    if surface in {"general", "dashboard"} and (metric_id or eon_id):
        raise ApiFault(400, "CONTEXT_INVALID", "Use a contextual entry point to scope a metric or application.")
    if surface in METRIC_SURFACES and not metric_id:
        raise ApiFault(400, "VALIDATION_FAILED", "A metric id is required for this context.")
    if surface in APPLICATION_SURFACES and not eon_id:
        raise ApiFault(400, "VALIDATION_FAILED", "An application id is required for this context.")
    if metric_id is not None:
        if not isinstance(metric_id, str) or not _METRIC.fullmatch(metric_id) or not _exists(
            "app.portfolio.services.metrics", ("get_metric", "metric_exists", "exists"), {"metricId": metric_id}, "METRIC_NOT_FOUND", "Metric was not found."
        ):
            raise ApiFault(404, "METRIC_NOT_FOUND", "Metric was not found.")
    if eon_id is not None:
        if not isinstance(eon_id, str) or not _EON.fullmatch(eon_id) or not _exists(
            "app.portfolio.services.applications",
            ("get_application", "application_exists", "exists"),
            {"eonId": eon_id},
            "APPLICATION_NOT_FOUND",
            "Application was not found.",
        ):
            raise ApiFault(404, "APPLICATION_NOT_FOUND", "Application was not found.")


def _filters(raw, month: str) -> dict:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    _reject_unknown(raw, {"month", "orgTree", "l1", "l2", "legalEntity", "tier", "risk", "lifecycle", "ma"}, "The request is not valid.")
    org = raw.get("orgTree") or "BUSINESS_ORG"
    if org not in {"BUSINESS_ORG", "BU"}:
        raise ApiFault(400, "UNKNOWN_FILTER_VALUE", "A filter value is not valid.", details={"field": "orgTree"})
    ma = raw.get("ma")
    if ma not in (None, "Y", "N"):
        raise ApiFault(400, "UNKNOWN_FILTER_VALUE", "A filter value is not valid.", details={"field": "ma"})
    tiers = raw.get("tier") or []
    if not isinstance(tiers, list) or len(tiers) > 50:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    clean_tiers = []
    for tier in tiers:
        if isinstance(tier, bool) or not isinstance(tier, int) or tier not in {1, 2, 3, 4}:
            raise ApiFault(400, "UNKNOWN_FILTER_VALUE", "A filter value is not valid.", details={"field": "tier"})
        if tier not in clean_tiers:
            clean_tiers.append(tier)
    clean_tiers.sort()
    return {
        "month": month,
        "orgTree": org,
        "l1": _strings(raw.get("l1"), "l1"),
        "l2": _strings(raw.get("l2"), "l2"),
        "legalEntity": _strings(raw.get("legalEntity"), "legalEntity"),
        "tier": clean_tiers,
        "risk": _strings(raw.get("risk"), "risk"),
        "lifecycle": _strings(raw.get("lifecycle"), "lifecycle"),
        "ma": ma,
    }


def _strings(values, field: str) -> list[str]:
    values = values or []
    if not isinstance(values, list) or len(values) > 50:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    cleaned = []
    for value in values:
        if not isinstance(value, str) or len(value) > 100:
            raise ApiFault(400, "UNKNOWN_FILTER_VALUE", "A filter value is not valid.", details={"field": field})
        text = sanitize(value, 100)
        if text and text not in cleaned:
            cleaned.append(text)
    cleaned.sort()
    return cleaned


def _filter_lines(filters: dict) -> list[str]:
    lines = [f"Organisation tree: {filters['orgTree']}."]
    labels = {
        "l1": "Level 1",
        "l2": "Level 2",
        "legalEntity": "Legal entity",
        "tier": "Tier",
        "risk": "Risk",
        "lifecycle": "Lifecycle",
        "ma": "Mergers and acquisitions",
    }
    for key, label in labels.items():
        value = filters.get(key)
        if value:
            rendered = ", ".join(sanitize(item, 40) for item in value) if isinstance(value, list) else sanitize(value, 40)
            lines.append(f"{label}: {rendered}.")
    if len(lines) == 1 and filters["orgTree"] == "BUSINESS_ORG":
        return ["No additional filters."]
    return lines[:12]


def _chips(metric_id, eon_id, month, month_source, portfolio) -> list[str]:
    chips = []
    if metric_id:
        chips.append(f"Metric {sanitize(metric_id, 20)}")
    if eon_id:
        chips.append(f"Application {sanitize(eon_id, 20)}")
    label = month_chip(month)
    if month_source == "latest_available":
        label = f"{label} (latest available)"
    chips.append(label)
    count = _count(_nested(portfolio.get("metric"), "coverage", "applications"))
    if count is None:
        count = _count(_nested(portfolio.get("overview"), "applicationsReporting"))
    if isinstance(count, int):
        chips.append(f"{count} applications")
    return chips


def _load_portfolio(surface, selected, month, metric_id, eon_id, filters) -> dict:
    needed = set(selected)
    found = {}
    request = _service_request(filters, month)
    if needed & {"portfolio_kpis", "attention_summary"}:
        from app.portfolio.services import dashboard

        found["overview"] = _read(lambda: dashboard.overview(request))
    if "portfolio_trend" in needed:
        from app.portfolio.services import dashboard

        found["trends"] = _read(lambda: dashboard.trends(request))
    if "org_contribution" in needed:
        from app.portfolio.services import dashboard

        found["org"] = _read(lambda: dashboard.org_contribution(request))
    if "data_coverage" in needed:
        from app.portfolio.services import dashboard

        found["coverage"] = _read(lambda: dashboard.data_coverage(request))
    if metric_id and needed & {"metric_kpis", "metric_definition"}:
        from app.portfolio.services import metrics

        found["metric"] = _read(lambda: metrics.preview(request, metric_id))
    if metric_id and "metric_trend" in needed:
        from app.portfolio.services import metrics

        found["metric_trend"] = _read(lambda: metrics.trend(request, metric_id))
    if metric_id and "metric_org_breakdown" in needed:
        from app.portfolio.services import metrics

        breakdown = _service_request(filters, month, {"dimension": "org", "level": "1", "pageSize": "8"})
        found["metric_breakdown"] = _read(lambda: metrics.breakdowns(breakdown, metric_id))
    if metric_id and "metric_applications" in needed:
        from app.portfolio.services import metrics

        sample = _service_request(filters, month, {"status": "Non_Compliant", "pageSize": "12"})
        found["metric_applications"] = _read(lambda: metrics.metric_applications(sample, metric_id))
    if eon_id and needed & {"application_attributes", "application_status", "application_peers", "owner_names"}:
        from app.portfolio.services import applications

        extra = {"includeOwners": "true"} if "owner_names" in needed else None
        detail = _service_request(filters, month, extra)
        found["application"] = _read(lambda: applications.detail(detail, eon_id))
    if eon_id and "application_history" in needed:
        from app.portfolio.services import applications

        history = _service_request(filters, None, {"metricId": metric_id} if metric_id else None)
        found["history"] = _read(lambda: applications.history(history, eon_id))
    return found


def _service_request(filters: dict | None, month: str | None, extra: dict | None = None):
    from types import SimpleNamespace
    from urllib.parse import urlencode

    from starlette.requests import Request

    from app.config import load_settings

    pairs: list[tuple[str, str]] = []
    if month:
        pairs.append(("month", month))
    for key in ("orgTree", "l1", "l2", "legalEntity", "tier", "risk", "lifecycle", "ma"):
        value = (filters or {}).get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            pairs.extend((key, str(item)) for item in value)
        else:
            pairs.append((key, str(value)))
    for key, value in (extra or {}).items():
        if value in (None, ""):
            continue
        if isinstance(value, list):
            pairs.extend((key, str(item)) for item in value)
        else:
            pairs.append((key, str(value)))
    app = SimpleNamespace(state=SimpleNamespace(settings=load_settings()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": urlencode(pairs).encode(),
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 8080),
            "app": app,
        }
    )


def _read(fn):
    try:
        value = fn()
    except Exception as exc:
        logger.info("portfolio reader failed error=%s", type(exc).__name__)
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict) and "data" in value and isinstance(value.get("meta"), dict):
        data = value["data"]
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        return data if isinstance(data, dict) else None
    return value if isinstance(value, dict) else None


def _registry():
    try:
        from app.portfolio.definitions import DEFINITIONS_VERSION, get as get_definition
    except ImportError:
        return "", None
    return str(DEFINITIONS_VERSION), get_definition


def _definition_line(getter, definition_id: str) -> str:
    if getter is None:
        return clip(f"{definition_id}: definition text is not loaded.")
    try:
        record = getter(definition_id)
    except TypeError:
        try:
            record = getter(id=definition_id)
        except Exception as exc:
            logger.info("definition read failed id=%s error=%s", definition_id, type(exc).__name__)
            return clip(f"{definition_id}: definition text is not available.")
    except Exception as exc:
        logger.info("definition read failed id=%s error=%s", definition_id, type(exc).__name__)
        return clip(f"{definition_id}: definition text is not available.")
    if record is None:
        return clip(f"{definition_id}: definition text is not available.")
    if hasattr(record, "model_dump"):
        record = record.model_dump()
    if not isinstance(record, dict):
        record = {
            "name": getattr(record, "name", ""),
            "definition": getattr(record, "definition", ""),
            "grain": getattr(record, "grain", ""),
            "scope": getattr(record, "scope", ""),
            "status": getattr(record, "status", ""),
            "limitations": getattr(record, "limitations", ""),
        }
    line = (
        f"{definition_id} {record.get('name') or ''} ({record.get('status') or ''}): "
        f"{record.get('definition') or ''} Grain: {record.get('grain') or ''}. "
        f"Scope: {record.get('scope') or ''}. Limitations: {record.get('limitations') or ''}."
    )
    return clip(line)


def _kpis(overview):
    if not isinstance(overview, dict):
        return None
    lines = []
    apps = _count(overview.get("applicationsReporting"))
    non = _count((overview.get("nonCompliant") or {}).get("applications") if isinstance(overview.get("nonCompliant"), dict) else None)
    if apps is not None:
        lines.append(f"Applications reporting: {apps}.")
    if non is not None:
        lines.append(f"Non-compliant applications: {non}.")
    testing = overview.get("testing") if isinstance(overview.get("testing"), dict) else {}
    without = _count(testing.get("withoutCompletedTest"))
    failed = _count(testing.get("withFailedTest"))
    if without is not None:
        lines.append(f"Applications with no completed test: {without}.")
    if failed is not None:
        lines.append(f"Applications with a failed test: {failed}.")
    findings = _count(overview.get("openFindings"))
    if findings is not None:
        lines.append(f"Open findings: {findings}.")
    return lines or None


def _attention(overview):
    if not isinstance(overview, dict):
        return None
    lines = []
    non = _count((overview.get("nonCompliant") or {}).get("applications") if isinstance(overview.get("nonCompliant"), dict) else None)
    testing = overview.get("testing") if isinstance(overview.get("testing"), dict) else {}
    movement = overview.get("movement") if isinstance(overview.get("movement"), dict) else {}
    if non is not None:
        lines.append(f"Non-compliant applications: {non}.")
    without = _count(testing.get("withoutCompletedTest"))
    failed = _count(testing.get("withFailedTest"))
    if without is not None:
        lines.append(f"No completed test: {without}.")
    if failed is not None:
        lines.append(f"Failed test: {failed}.")
    if isinstance(movement.get("newlyNonCompliant"), int):
        lines.append(f"Newly non-compliant: {movement['newlyNonCompliant']}.")
    return lines or None


def _coverage(coverage):
    if not isinstance(coverage, dict):
        return None
    lines = []
    for key, label in (
        ("applicationsReporting", "Applications reporting"),
        ("applicationsInDataset", "Applications in the dataset"),
        ("metricsInDataset", "Metrics in the dataset"),
    ):
        value = coverage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            lines.append(f"{label}: {value}.")
    return lines or None


_BAND_NAMES = {"green": "Green (healthy)", "amber": "Amber (watch)", "red": "Red (needs attention)"}


def _band_line(rate, rag):
    """The central provisional band and its direction, so a narrative cannot invent its own."""

    from app.portfolio.definitions import RATE_AMBER_BELOW, RATE_GREEN_BELOW

    name = _BAND_NAMES.get(str(rag)) if rate is not None else None
    if not name:
        return None
    return (
        f"Provisional band: {name}. Green is below {RATE_GREEN_BELOW:.0%}, amber is below {RATE_AMBER_BELOW:.0%}, "
        "and red is from that point up. A higher rate is worse. The band is provisional, not a client target, "
        "and the business meaning of the numerator is unconfirmed."
    )


def _metric_kpis(preview):
    if not isinstance(preview, dict):
        return None
    rate = preview.get("rate") if isinstance(preview.get("rate"), dict) else None
    if not rate:
        return None
    lines = []
    numerator = rate.get("numerator")
    denominator = rate.get("denominator")
    value = rate.get("rate")
    if numerator is not None and denominator is not None:
        lines.append(f"Numerator {numerator}, denominator {denominator}, provisional rate {value}.")
    band = _band_line(value, preview.get("rag"))
    if band:
        lines.append(band)
    compliance = preview.get("compliance") if isinstance(preview.get("compliance"), dict) else {}
    coverage = preview.get("coverage") if isinstance(preview.get("coverage"), dict) else {}
    if isinstance(compliance.get("nonCompliant"), int) and not isinstance(compliance.get("nonCompliant"), bool):
        lines.append(f"Non-compliant metric rows: {compliance['nonCompliant']}.")
    if isinstance(coverage.get("applications"), int) and not isinstance(coverage.get("applications"), bool):
        lines.append(f"Metric rows in scope: {coverage['applications']}.")
    prior = rate.get("priorRate")
    if prior is not None:
        lines.append(f"Prior provisional rate {prior}. Change {rate.get('deltaPp')} percentage points.")
    return lines or None


def _series(payload, key):
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return None
    points = payload[key]
    if not points:
        return None
    lines = [f"Series length: {len(points)}."]
    for item in points:
        if not isinstance(item, dict) or item.get("observed") is False or not item.get("month"):
            continue
        rate = item.get("rate")
        if rate is None:
            continue
        lines.append(f"{sanitize(item.get('month'), 20)}: provisional rate {rate}.")
        if len(lines) >= 4:
            break
    return lines


def _named_counts(payload, key, count_key):
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return None
    lines = []
    for item in payload[key][:8]:
        if not isinstance(item, dict):
            continue
        label = sanitize(item.get("label") or item.get("key") or "", 40)
        count = item.get(count_key)
        if label and isinstance(count, int) and not isinstance(count, bool):
            lines.append(f"{label}: {count}.")
    return lines or None


def _applications(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return None
    lines = []
    for item in payload["items"][:12]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"{sanitize(item.get('eonId'), 20)} {sanitize(item.get('applicationName'), 40)} "
            f"{sanitize(item.get('complianceReason'), 40)}."
        )
    return lines or None


def _attributes(detail):
    if not isinstance(detail, dict):
        return None
    attributes = detail.get("attributes") if isinstance(detail.get("attributes"), dict) else detail
    if not isinstance(attributes, dict):
        return None
    lines = []
    for key, label in (("tier", "Tier"), ("risk", "Risk"), ("lifecycle", "Lifecycle"), ("legalEntityCode", "Legal entity")):
        if attributes.get(key) is not None:
            lines.append(f"{label}: {sanitize(attributes.get(key), 40)}.")
    return lines or None


def _application_status(detail):
    status = detail.get("status") if isinstance(detail, dict) else None
    if not isinstance(status, dict):
        return None
    lines = []
    for key, label in (
        ("isNonCompliant", "Non-compliant"),
        ("hasNoCompletedTest", "No completed test"),
        ("hasFailedTest", "Failed test"),
        ("openFindings", "Open findings"),
        ("metricRows", "Metric rows"),
    ):
        if key in status and status[key] is not None:
            lines.append(f"{label}: {sanitize(status[key], 40)}.")
    return lines or None


def _history(history):
    if not isinstance(history, dict) or not isinstance(history.get("months"), list):
        return None
    months = history["months"]
    observed = sum(1 for item in months if isinstance(item, dict) and item.get("observed") is True)
    return [f"Observed in {observed} of {len(months)} months in the returned history."]


def _peers(detail):
    peers = detail.get("peers") if isinstance(detail, dict) else None
    if not isinstance(peers, dict):
        return None
    apps = peers.get("applications")
    non = peers.get("nonCompliantApplications")
    if not isinstance(apps, int):
        return None
    return [f"Peer applications: {apps}. Non-compliant peers: {non}."]


def _owners(detail):
    attributes = detail.get("attributes") if isinstance(detail, dict) else None
    owners = None
    if isinstance(attributes, dict):
        owners = attributes.get("owners")
    if owners is None and isinstance(detail, dict):
        owners = detail.get("owners")
    if not isinstance(owners, dict):
        return ["Owner names were requested and were not available."]
    lines = []
    if owners.get("business"):
        lines.append(f"Business owner: {sanitize(owners.get('business'), 80)}.")
    if owners.get("it"):
        lines.append(f"IT owner: {sanitize(owners.get('it'), 80)}.")
    return lines or ["Owner names were requested and were not available."]


def _ids_for(key: str) -> list[str]:
    return {
        "portfolio_kpis": ["PD-03", "PD-08"],
        "attention_summary": ["PD-03", "PD-04", "PD-05"],
        "data_coverage": ["PD-18"],
        "metric_kpis": ["PD-01", "PD-16"],
        "metric_definition": ["PD-01", "PD-02"],
        "application_peers": ["PD-17"],
        "owner_names": [],
    }.get(key, [])


def _count(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("value"), int) and not isinstance(value.get("value"), bool):
        return value["value"]
    return None


def _nested(payload, *path):
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _exists(module: str, names: tuple[str, ...], scope: dict, code: str, message: str) -> bool:
    try:
        imported = importlib.import_module(module)
    except ImportError:
        return True
    for name in names:
        fn = getattr(imported, name, None)
        if not callable(fn):
            continue
        try:
            result = fn(scope)
        except Exception as exc:
            logger.info("lookup failed module=%s error=%s", module, type(exc).__name__)
            raise ApiFault(503, "DATA_SOURCE_UNAVAILABLE", "The identifier could not be checked.", retryable=True) from exc
        return not (result is None or result is False)
    return True


def _call(module: str, names: tuple[str, ...], scope: dict):
    try:
        imported = importlib.import_module(module)
    except ImportError:
        return None
    for name in names:
        fn = getattr(imported, name, None)
        if not callable(fn):
            continue
        try:
            value = fn(scope)
        except TypeError:
            logger.info("portfolio reader skipped module=%s", module)
            return None
        except Exception as exc:
            logger.info("portfolio reader failed module=%s error=%s", module, type(exc).__name__)
            return None
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        if isinstance(value, dict) and "data" in value and "meta" in value:
            value = value["data"]
            if hasattr(value, "model_dump"):
                value = value.model_dump()
        return value
    return None


def _latest_month() -> str | None:
    try:
        from app.portfolio.month import resolve_month
    except ImportError:
        return None
    try:
        result = resolve_month(None)
    except TypeError:
        try:
            result = resolve_month()
        except Exception as exc:
            logger.info("month resolve failed error=%s", type(exc).__name__)
            return None
    except Exception as exc:
        logger.info("month resolve failed error=%s", type(exc).__name__)
        return None
    if isinstance(result, str) and _month_end(result):
        return result
    if isinstance(result, tuple) and result and isinstance(result[0], str) and _month_end(result[0]):
        return result[0]
    if isinstance(result, dict):
        for key in ("month", "latestMonth"):
            if isinstance(result.get(key), str) and _month_end(result[key]):
                return result[key]
    return None


def _known_month(month: str) -> None:
    try:
        from app.portfolio.month import known_month
    except ImportError:
        return
    try:
        known = known_month(month)
    except Exception as exc:
        logger.info("month check failed error=%s", type(exc).__name__)
        return
    if known is False:
        raise ApiFault(400, "UNKNOWN_MONTH", "The reporting month is not a known month-end.")


def _promoted_at() -> str | None:
    for module, names in (
        ("app.portfolio.cache", ("dataset_meta", "current_dataset")),
        ("app.portfolio.services.status", ("status", "portfolio_status")),
    ):
        value = _call(module, names, {})
        if isinstance(value, dict):
            dataset = value.get("dataset") if isinstance(value.get("dataset"), dict) else value
            promoted = dataset.get("promotedAt") if isinstance(dataset, dict) else None
            if isinstance(promoted, str):
                return promoted
    return None


def _month_end(value: str) -> bool:
    if not _MONTH.fullmatch(value):
        return False
    try:
        year, month, day = (int(part) for part in value.split("-"))
        return day == calendar.monthrange(year, month)[1]
    except (ValueError, calendar.IllegalMonthError):
        return False


def _reject_unknown(payload: dict, allowed: set[str], message: str) -> None:
    unknown = [key for key in payload if key not in allowed]
    if unknown:
        raise ApiFault(400, "VALIDATION_FAILED", message, details={"fields": unknown})
