"""Pure shaping helpers. Formulas stay in definitions.py."""

from __future__ import annotations

import math
from urllib.parse import urlencode

from app.portfolio import definitions
from app.portfolio.coerce import as_bool, as_int
from app.portfolio.definitions import flag
from app.portfolio.month import previous_calendar_month


def count_value(value, prior) -> dict:
    current = 0 if value is None else int(value)
    if prior is None:
        return {"value": current, "prior": None, "delta": None}
    previous = int(prior)
    return {"value": current, "prior": previous, "delta": current - previous}


def share_value(part, whole, prior_part, prior_whole) -> dict:
    current = definitions.share(part or 0, whole or 0)
    if prior_part is None or prior_whole is None:
        prior = None
    else:
        prior = definitions.share(prior_part, prior_whole)
    return {
        "value": current,
        "prior": prior,
        "deltaPp": definitions.rate_change_pp(current, prior),
        "definitionId": "PD-08",
    }


def rate_value(numerator, denominator, prior_numerator=None, prior_denominator=None) -> dict:
    numer = int(numerator or 0)
    denom = int(denominator or 0)
    current = definitions.provisional_rate(numer, denom)
    if prior_numerator is None or prior_denominator is None:
        prior = None
    else:
        prior = definitions.provisional_rate(int(prior_numerator), int(prior_denominator))
    return {
        "numerator": numer,
        "denominator": denom,
        "rate": current,
        "priorRate": prior,
        "deltaPp": definitions.rate_change_pp(current, prior),
        "definitionId": "PD-01",
    }


def paginate(items: list, page: int, page_size: int) -> tuple[list, dict]:
    total = len(items)
    total_pages = math.ceil(total / page_size) if page_size else 0
    start = (page - 1) * page_size
    return items[start : start + page_size], {
        "page": page,
        "pageSize": page_size,
        "totalItems": total,
        "totalPages": total_pages,
    }


def sort_by(items: list, value_fn, reverse: bool, tie_fn) -> list:
    ordered = list(items)
    ordered.sort(key=tie_fn)
    present = [item for item in ordered if value_fn(item) is not None]
    missing = [item for item in ordered if value_fn(item) is None]
    present.sort(key=value_fn, reverse=reverse)
    return present + missing


def org_ref(tree: str, level1: str | None, level2: str | None = None) -> dict:
    return {"tree": tree, "level1": level1 or "", "level2": level2}


def zeros() -> dict:
    return {
        "APPLICATIONS_REPORTING": 0,
        "NON_COMPLIANT": 0,
        "NO_TEST": 0,
        "FAILED": 0,
        "OPEN_FINDINGS": 0,
        "METRIC_ROWS": 0,
        "NEWLY": 0,
        "RESOLVED": 0,
        "PERSISTENT": 0,
        "NO_PRIOR": 0,
        "NOT_BOTH": 0,
    }


def movement_block(row: dict | None, *, enabled: bool) -> dict | None:
    if not enabled or row is None:
        return None
    return {
        "newlyNonCompliant": int(row.get("NEWLY") or 0),
        "resolved": int(row.get("RESOLVED") or 0),
        "persistentNonCompliant": int(row.get("PERSISTENT") or 0),
        "noPriorMonth": int(row.get("NO_PRIOR") or 0),
        "notNonCompliantBothMonths": int(row.get("NOT_BOTH") or 0),
    }


def metric_movement_counts(rows: list[dict] | None) -> dict | None:
    if rows is None:
        return None
    counts = {
        "newlyNonCompliant": 0,
        "resolved": 0,
        "persistentNonCompliant": 0,
        "noPriorMonth": 0,
        "other": 0,
    }
    mapping = {
        "NEWLY_NON_COMPLIANT": "newlyNonCompliant",
        "RESOLVED": "resolved",
        "PERSISTENT_NON_COMPLIANT": "persistentNonCompliant",
        "NO_PRIOR_MONTH": "noPriorMonth",
        "OTHER": "other",
    }
    for row in rows:
        key = mapping.get(row["MOVEMENT"])
        if key:
            counts[key] += int(row["N"] or 0)
    return counts


def compliance_counts(row: dict | None) -> dict:
    row = row or {}
    return {
        "compliant": int(row.get("COMPLIANT") or 0),
        "nonCompliant": int(row.get("NON_COMPLIANT") or 0),
        "pending": int(row.get("PENDING") or 0),
        "notApplicable": int(row.get("NOT_APPLICABLE") or 0),
    }


def test_counts(row: dict | None) -> dict:
    row = row or {}
    return {
        "complete": int(row.get("TEST_COMPLETE") or 0),
        "pending": int(row.get("TEST_PENDING") or 0),
        "none": int(row.get("TEST_NONE") or 0),
        "exempt": int(row.get("TEST_EXEMPT") or 0),
    }


def nc_since(observed: dict[str, bool], month: str, first_month: str) -> str | None:
    """Start of the current unbroken non-compliant run. None when it is not derivable."""
    if observed.get(month) is not True:
        return None
    start = month
    cursor = month
    while True:
        prior = previous_calendar_month(cursor)
        if observed.get(prior) is True:
            cursor = prior
            start = prior
            continue
        break
    if start == first_month:
        return None
    return start


def nc_run(observed: dict[str, bool], month: str, first_month: str) -> dict | None:
    if observed.get(month) is not True:
        return None
    count = 0
    cursor = month
    start = month
    while observed.get(cursor) is True:
        count += 1
        start = cursor
        prior = previous_calendar_month(cursor)
        if observed.get(prior) is not True:
            break
        cursor = prior
    return {"months": count, "since": None if start == first_month else start}


def metric_flags(denominator: int, prior_rows: int | None, *, no_rows: bool = False) -> list[dict]:
    flags = [
        flag("RATE_PROVISIONAL"),
        flag("DENOMINATOR_SCOPE_INFERRED"),
        flag("FAMILY_NOT_AVAILABLE"),
    ]
    if denominator < 20:
        flags.append(flag("SMALL_BASE"))
    if prior_rows == 0:
        flags.append(flag("NO_PRIOR_MONTH"))
    if no_rows:
        flags.append(flag("NO_ROWS_IN_MONTH"))
    return flags


def metric_links(metric_id: str, month: str) -> dict:
    return {
        "summary": f"/register/{metric_id}?month={month}",
        "investigation": f"/investigate/metrics/{metric_id}?month={month}",
    }


def source_urls(metric_id: str, scope) -> dict:
    pairs = [("month", scope.resolved_month), ("orgTree", scope.org_tree)]
    for name, values in (
        ("l1", scope.l1),
        ("l2", scope.l2),
        ("legalEntity", scope.legal_entity),
        ("tier", scope.tier),
        ("risk", scope.risk),
        ("lifecycle", scope.lifecycle),
    ):
        for value in values:
            pairs.append((name, value))
    if scope.ma:
        pairs.append(("ma", scope.ma))
    query = urlencode(pairs)
    base = f"/api/v1/portfolio/metrics/{metric_id}"
    trend_pairs = [(key, value) for key, value in pairs if key != "month"]
    return {
        "applicationsUrl": f"{base}/applications?{query}",
        "breakdownsUrl": f"{base}/breakdowns?{query}&dimension=org",
        "trendUrl": f"{base}/trend?{urlencode(trend_pairs)}" if trend_pairs else f"{base}/trend",
    }


def application_org(row: dict, tree: str) -> dict:
    if tree == "BU":
        return org_ref(tree, row.get("BU_SUPER_DIVISION"), row.get("BU_DIVISION"))
    return org_ref(tree, row.get("SUPER_DIVISION"), row.get("DIVISION"))


def bool_flag(row: dict, column: str) -> bool:
    return as_bool(row.get(column))


def nullable_int(value) -> int | None:
    return as_int(value)
