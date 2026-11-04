"""Scope filters, paging and sort. Values are checked here; SQL only sees bound parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.common.v2_errors import not_found, validation

_MONTH = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_./+ -]{1,100}$")
_SORT = re.compile(r"^([A-Za-z][A-Za-z0-9]*):(asc|desc)$")
_METRIC = re.compile(r"^M[0-9]{6}$")
_EON = re.compile(r"^EON[0-9]{6}$")

ORG_TREES = ("BUSINESS_ORG", "BU")
ATTENTION = (
    "nonCompliant",
    "noCompletedTest",
    "failedTest",
    "newlyNonCompliant",
    "resolved",
    "persistentNonCompliant",
)
COMPLIANCE_STATUS = ("Compliant", "Non_Compliant", "Pending", "Not_Applicable")
TEST_STATUS = ("Test_Complete", "No_Test", "Test_Pending", "Exempt")
DISTRIBUTION_DIMENSIONS = ("risk", "tier", "lifecycle", "rto", "legalEntity")
BREAKDOWN_DIMENSIONS = ("org", "legalEntity", "tier", "risk", "lifecycle", "complianceReason", "testStatus")

SCOPE_KEYS = ("month", "orgTree", "l1", "l2", "legalEntity", "tier", "risk", "lifecycle", "ma")

ORG_SORT = {"nonCompliant", "share", "reporting", "openFindings", "name"}
APP_SORT = {"name", "openFindings", "metricRows", "org"}
METRIC_SORT = {"metricId", "applications", "nonCompliant", "rate", "rateDelta", "rag"}
BREAK_SORT = {"applications", "nonCompliant", "rate", "key"}
METRIC_APP_SORT = {"name", "status", "rfb", "openFindings"}


@dataclass(frozen=True)
class Scope:
    org_tree: str = "BUSINESS_ORG"
    l1: tuple[str, ...] = ()
    l2: tuple[str, ...] = ()
    legal_entity: tuple[str, ...] = ()
    tier: tuple[int, ...] = ()
    risk: tuple[str, ...] = ()
    lifecycle: tuple[str, ...] = ()
    ma: str | None = None
    month: str | None = None
    resolved_month: str | None = None
    month_source: str | None = None

    def with_resolved(self, month: str, source: str) -> Scope:
        return replace(self, resolved_month=month, month_source=source)

    def unfiltered(self) -> bool:
        return self.org_tree == "BUSINESS_ORG" and not (
            self.l1 or self.l2 or self.legal_entity or self.tier or self.risk or self.lifecycle or self.ma
        )

    def active(self) -> dict:
        return {
            "month": self.resolved_month or self.month,
            "orgTree": self.org_tree,
            "l1": list(self.l1),
            "l2": list(self.l2),
            "legalEntity": list(self.legal_entity),
            "tier": list(self.tier),
            "risk": list(self.risk),
            "lifecycle": list(self.lifecycle),
            "ma": self.ma,
        }

    def cache_params(self, extra: dict | None = None) -> dict:
        params = self.active()
        params["month"] = self.resolved_month or self.month
        if extra:
            params.update(extra)
        return params


def query_lists(request) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        found.setdefault(key, []).append(value)
    return found


def unknown_warnings(params: dict[str, list[str]], allowed: set[str]) -> list[dict]:
    extra = sorted({key for key in params if key not in allowed})
    if not extra:
        return []
    shown = ", ".join(key[:40] for key in extra[:10])
    return [{"code": "UNKNOWN_PARAMETER", "message": f"Ignored unknown parameter: {shown}."}]


def one(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name) or []
    if not values:
        return None
    if len(values) > 1:
        raise validation(f"{name} may be provided once.", field=name)
    return values[0]


def parse_scope(params: dict[str, list[str]]) -> Scope:
    org_tree = one(params, "orgTree") or "BUSINESS_ORG"
    if org_tree not in ORG_TREES:
        raise validation("orgTree must be BUSINESS_ORG or BU.", field="orgTree")
    month = one(params, "month")
    if month is not None:
        month = month.strip()
        if month == "":
            month = None
        elif not _MONTH.fullmatch(month) or not _is_month_end(month):
            raise validation("month must be a known month-end.", code="UNKNOWN_MONTH", field="month", field_code="UNKNOWN_MONTH")
    ma_values = _tokens(params, "ma")
    ma = None
    if ma_values:
        if len(ma_values) > 1 or ma_values[0] not in {"Y", "N"}:
            raise validation("ma is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="ma", field_code="UNKNOWN_FILTER_VALUE")
        ma = ma_values[0]
    tiers = []
    for value in _tokens(params, "tier"):
        if value not in {"1", "2", "3", "4"}:
            raise validation("tier is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="tier", field_code="UNKNOWN_FILTER_VALUE")
        tiers.append(int(value))
    return Scope(
        org_tree=org_tree,
        l1=tuple(_tokens(params, "l1")),
        l2=tuple(_tokens(params, "l2")),
        legal_entity=tuple(_tokens(params, "legalEntity")),
        tier=tuple(tiers),
        risk=tuple(_tokens(params, "risk")),
        lifecycle=tuple(_tokens(params, "lifecycle")),
        ma=ma,
        month=month,
    )


def validate_scope_values(scope: Scope, catalog: dict) -> None:
    _members("risk", scope.risk, set(catalog["risks"]))
    _members("lifecycle", scope.lifecycle, set(catalog["lifecycles"]))
    _members("legalEntity", scope.legal_entity, set(catalog["legalEntities"]))
    tree = catalog["trees"][scope.org_tree]
    _members("l1", scope.l1, set(tree["level1"]))
    _members("l2", scope.l2, set(tree["level2"]))


def parse_optional_month(params: dict[str, list[str]], name: str) -> str | None:
    value = one(params, name)
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if not _MONTH.fullmatch(value) or not _is_month_end(value):
        raise validation(
            f"{name} must be a known month-end.",
            code="UNKNOWN_MONTH",
            field=name,
            field_code="UNKNOWN_MONTH",
        )
    return value


def ensure_month(month: str, months: list[str]) -> None:
    if month not in months:
        raise validation("month must be a known month-end.", code="UNKNOWN_MONTH", field="month", field_code="UNKNOWN_MONTH")


def parse_sort(value: str | None, allowed: set[str], default: tuple[str, str]) -> tuple[str, str]:
    if value is None or value == "":
        return default
    match = _SORT.fullmatch(value.strip())
    if not match or match.group(1) not in allowed:
        raise validation(
            "That sort field is not supported.",
            code="UNSUPPORTED_SORT",
            field="sort",
            field_code="UNSUPPORTED_SORT",
        )
    return match.group(1), match.group(2)


def parse_page(params: dict[str, list[str]], *, default_size: int = 25) -> tuple[int, int]:
    page = _int_param(one(params, "page"), "page", 1)
    size = _int_param(one(params, "pageSize"), "pageSize", default_size)
    if page < 1:
        raise validation("page must be at least 1.", field="page")
    if size < 1 or size > 100:
        raise validation("pageSize must be between 1 and 100.", field="pageSize")
    return page, size


def parse_q(params: dict[str, list[str]]) -> str | None:
    value = one(params, "q")
    if value is None or value == "":
        return None
    if len(value) > 40:
        raise validation("q must be at most 40 characters.", field="q", field_code="TOO_LONG")
    return value


def parse_bool(params: dict[str, list[str]], name: str, *, default: bool = False) -> bool:
    value = one(params, name)
    if value is None or value == "":
        return default
    if value == "true":
        return True
    if value == "false":
        return False
    raise validation(f"{name} must be true or false.", field=name)


def parse_choice(params: dict[str, list[str]], name: str, allowed: set[str] | tuple[str, ...]) -> str | None:
    value = one(params, name)
    if value is None or value == "":
        return None
    if value not in allowed:
        raise validation(f"{name} is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field=name, field_code="UNKNOWN_FILTER_VALUE")
    return value


def parse_repeat(params: dict[str, list[str]], name: str, allowed: set[str] | None) -> tuple[str, ...]:
    values = _tokens(params, name)
    if allowed is not None:
        _members(name, values, set(allowed))
    return tuple(values)


def parse_level(params: dict[str, list[str]]) -> int:
    value = one(params, "level")
    if value is None or value == "":
        return 1
    if value not in {"1", "2"}:
        raise validation("level must be 1 or 2.", field="level")
    return int(value)


def parse_parent(params: dict[str, list[str]], *, level: int) -> str | None:
    parent = one(params, "parent")
    if parent is None or parent == "":
        return None
    if level != 2:
        raise validation("parent is only valid with level 2.", field="parent")
    if len(parent) > 100 or not _TOKEN.fullmatch(parent):
        raise validation("parent is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="parent", field_code="UNKNOWN_FILTER_VALUE")
    return parent


def parse_metric_id(metric_id: str) -> str:
    if not _METRIC.fullmatch(metric_id or ""):
        raise not_found("METRIC_NOT_FOUND", "Metric was not found.")
    return metric_id


def parse_eon_id(eon_id: str) -> str:
    if not _EON.fullmatch(eon_id or ""):
        raise not_found("APPLICATION_NOT_FOUND", "Application was not found.")
    return eon_id


def reject_own_filter(dimension: str, scope: Scope) -> None:
    owned = {
        "risk": scope.risk,
        "tier": scope.tier,
        "lifecycle": scope.lifecycle,
        "legalEntity": scope.legal_entity,
    }.get(dimension)
    if owned:
        raise validation(
            "Do not filter on the same dimension being distributed.",
            field=dimension,
        )


def _tokens(params: dict[str, list[str]], name: str) -> list[str]:
    values = params.get(name) or []
    if len(values) > 50:
        raise validation(f"{name} accepts at most 50 values.", field=name, field_code="TOO_MANY")
    cleaned = []
    for value in values:
        if len(value) > 100:
            raise validation(f"{name} values must be at most 100 characters.", field=name, field_code="TOO_LONG")
        if not _TOKEN.fullmatch(value):
            raise validation(
                f"{name} is not an allowed value.",
                code="UNKNOWN_FILTER_VALUE",
                field=name,
                field_code="UNKNOWN_FILTER_VALUE",
            )
        cleaned.append(value)
    return cleaned


def _members(field: str, values: tuple[str, ...] | list[str], allowed: set[str]) -> None:
    for value in values:
        if value not in allowed:
            raise validation(
                f"{field} is not an allowed value.",
                code="UNKNOWN_FILTER_VALUE",
                field=field,
                field_code="UNKNOWN_FILTER_VALUE",
            )


def _int_param(value: str | None, field: str, default: int) -> int:
    if value is None or value == "":
        return default
    if not re.fullmatch(r"[0-9]+", value):
        raise validation(f"{field} must be a whole number.", field=field)
    return int(value)


def _is_month_end(value: str) -> bool:
    from datetime import date, timedelta

    try:
        year, month, day = (int(part) for part in value.split("-"))
        found = date(year, month, day)
    except ValueError:
        return False
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    return found == next_first - timedelta(days=1)
