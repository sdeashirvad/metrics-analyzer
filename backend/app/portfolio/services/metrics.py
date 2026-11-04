"""Metric register, preview, summary, trend, breakdowns and contributing applications."""

from __future__ import annotations

from app.common.v2_errors import not_found, validation
from app.portfolio import lineage, repository
from app.portfolio.definitions import (
    DENOMINATOR_RULE,
    NUMERATOR_RULE,
    classify_denominator,
    get,
    metric_movement,
    RAG_RANK,
    RAG_VALUES,
    classify_rate,
    provisional_rate,
    share,
)
from app.portfolio.month import prior_in_index
from app.portfolio.scope import (
    BREAKDOWN_DIMENSIONS,
    BREAK_SORT,
    COMPLIANCE_STATUS,
    METRIC_APP_SORT,
    METRIC_SORT,
    SCOPE_KEYS,
    TEST_STATUS,
    ensure_month,
    one,
    parse_bool,
    parse_metric_id,
    parse_optional_month,
    parse_page,
    parse_q,
    parse_repeat,
    parse_sort,
)
from app.portfolio.services.dashboard import _run, _scoped
from app.portfolio.support import (
    application_org,
    compliance_counts,
    metric_flags,
    metric_links,
    metric_movement_counts,
    paginate,
    rate_value,
    sort_by,
    test_counts,
)

_SCOPE = set(SCOPE_KEYS)
_DENOM = {"INCLUDES_PENDING", "EXCLUDES_PENDING", "MIXED", "UNDETERMINED"}
_STATUS_RANK = {"Non_Compliant": 0, "Pending": 1, "Compliant": 2, "Not_Applicable": 3}


def register(request):
    params, scope, warnings = _scoped(request, _SCOPE | {"q", "hasNonCompliant", "denominatorScope", "rag", "sort", "page", "pageSize"})
    query = parse_q(params)
    has_nc = parse_bool(params, "hasNonCompliant", default=False)
    scopes = parse_repeat(params, "denominatorScope", _DENOM)
    rags = parse_repeat(params, "rag", set(RAG_VALUES))
    sort_field, direction = parse_sort(one(params, "sort"), METRIC_SORT, ("applications", "desc"))
    page, page_size = parse_page(params)

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        prior = prior_in_index(month, probe["months"])
        grouped = _group(repository.metric_month_aggregates(connection, resolved))
        movements = {}
        if prior:
            for row in repository.metric_movements(connection, resolved, month, prior):
                movements.setdefault(row["METRIC_ID"], []).append(row)
        items = []
        matched_catalog = 0
        with_rows = 0
        for metric_id, meta in catalog["metrics"].items():
            if query and query.upper() not in metric_id.upper():
                continue
            if scopes and meta["denominatorScope"] not in scopes:
                continue
            matched_catalog += 1
            months = grouped.get(metric_id, {})
            if month not in months:
                continue
            with_rows += 1
            current = months[month]
            if has_nc and int(current["NON_COMPLIANT"] or 0) == 0:
                continue
            item = _register_item(metric_id, meta, months, month, prior, probe["months"], movements.get(metric_id))
            if rags and item["rag"] not in rags:
                continue
            items.append(item)
        items = _sort_register(items, sort_field, direction)
        page_items, page_block = paginate(items, page, page_size)
        return {
            "data": {
                "month": month,
                "previousMonth": prior,
                "items": page_items,
                "page": page_block,
                "totals": {"metrics": matched_catalog, "metricsWithRowsInMonth": with_rows},
            },
            "warnings": warnings,
            "asOf": month,
            "lineage": lineage.rate(),
        }

    extra = {
        "q": query,
        "hasNonCompliant": has_nc,
        "denominatorScope": list(scopes),
        "rag": list(rags),
        "sort": f"{sort_field}:{direction}",
        "page": page,
        "pageSize": page_size,
    }
    return _run(request, "metrics", {**scope.cache_params(), **extra}, scope, produce, _no_fallback, lineage=lineage.rate())


def preview(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, _SCOPE)
    return _run(
        request,
        f"metrics/{metric_id}/preview",
        scope.cache_params(),
        scope,
        lambda connection, probe, catalog, resolved: _preview_payload(connection, probe, catalog, resolved, metric_id, warnings, summary=False),
        _no_fallback,
        lineage=lineage.rate(),
    )


def summary(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, _SCOPE)

    def produce(connection, probe, catalog, resolved):
        body = _preview_payload(connection, probe, catalog, resolved, metric_id, warnings, summary=True)
        preview_data = body["data"]
        month = resolved.resolved_month
        prior = preview_data["previousMonth"]
        months = _group(repository.metric_month_aggregates(connection, resolved, metric_id)).get(metric_id, {})
        current = months.get(month) or {}
        rows = repository.metric_application_rows(connection, resolved, metric_id, month, prior)
        reasons = {}
        for row in rows:
            bucket = reasons.setdefault(row.get("COMPLIANCE_REASON") or "", {"key": row.get("COMPLIANCE_REASON") or "", "rows": 0, "nonCompliantRows": 0})
            bucket["rows"] += 1
            if row.get("COMPLIANCE_STATUS") == "Non_Compliant":
                bucket["nonCompliantRows"] += 1
        contributors = [item for item in (_application_row(row, resolved.org_tree) for row in rows) if item["complianceStatus"] == "Non_Compliant"]
        contributors = sort_by(contributors, lambda item: item["openFindings"], True, lambda item: item["eonId"])[:10]
        total = int(current.get("APPLICATIONS") or 0)
        compliance = preview_data["compliance"]
        testing = preview_data["testing"]
        return {
            "data": {
                "preview": preview_data,
                "calculation": {
                    "formula": get("PD-01")["definition"],
                    "steps": [
                        {"label": "Rows in scope", "value": total},
                        {"label": "Rows in denominator", "value": preview_data["rate"]["denominator"]},
                        {"label": "Rows in numerator", "value": preview_data["rate"]["numerator"]},
                        {"label": "Rate", "value": preview_data["rate"]["rate"], "note": "Provisional. Null when the denominator is 0."},
                    ],
                    "excludedRows": {
                        "notApplicable": compliance["notApplicable"],
                        "pendingExcluded": int(current.get("PENDING_EXCLUDED") or 0),
                        "pendingIncluded": int(current.get("PENDING_INCLUDED") or 0),
                    },
                },
                "distributions": {
                    "byComplianceStatus": _shares([
                        ("Compliant", compliance["compliant"]),
                        ("Non_Compliant", compliance["nonCompliant"]),
                        ("Pending", compliance["pending"]),
                        ("Not_Applicable", compliance["notApplicable"]),
                    ], total),
                    "byTestStatus": _shares([
                        ("Test_Complete", testing["complete"]),
                        ("Test_Pending", testing["pending"]),
                        ("No_Test", testing["none"]),
                        ("Exempt", testing["exempt"]),
                    ], total),
                    "byComplianceReason": sorted(reasons.values(), key=lambda item: (-item["rows"], item["key"])),
                },
                "topContributors": {"nonCompliantApplications": contributors},
                "availableMonths": sorted(months),
                "provisional": [
                    {"definitionId": item_id, "statement": get(item_id)["definition"]}
                    for item_id in ("PD-01", "PD-02", "PD-13", "PD-14", "PD-15", "PD-16")
                ],
            },
            "warnings": warnings,
            "asOf": month,
            "lineage": lineage.rate(),
        }

    return _run(request, f"metrics/{metric_id}", scope.cache_params(), scope, produce, _no_fallback, lineage=lineage.rate())


def trend(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, _SCOPE | {"from", "to"})
    month_from = parse_optional_month(params, "from")
    month_to = parse_optional_month(params, "to")

    def produce(connection, probe, catalog, resolved):
        _require_metric(connection, catalog, metric_id)
        if month_from:
            ensure_month(month_from, probe["months"])
        if month_to:
            ensure_month(month_to, probe["months"])
        months = _group(repository.metric_month_aggregates(connection, resolved, metric_id)).get(metric_id, {})
        eon_rows = repository.metric_eon_rows(connection, resolved, metric_id)
        by_month_eon: dict[str, list] = {}
        for row in eon_rows:
            by_month_eon.setdefault(row["MONTH_END"], []).append(row)
        points = []
        composition = []
        for month in probe["months"]:
            if month_from and month < month_from:
                continue
            if month_to and month > month_to:
                continue
            row = months.get(month)
            if row is None:
                points.append({"month": month, "observed": False})
            else:
                points.append({
                    "month": month,
                    "observed": True,
                    "applications": int(row["APPLICATIONS"] or 0),
                    "numerator": int(row["NUMERATOR"] or 0),
                    "denominator": int(row["DENOMINATOR"] or 0),
                    "rate": provisional_rate(int(row["NUMERATOR"] or 0), int(row["DENOMINATOR"] or 0)),
                    "nonCompliantApplications": int(row["NON_COMPLIANT"] or 0),
                    "complianceRows": compliance_counts(row),
                    "testRows": test_counts(row),
                })
            prior = prior_in_index(month, probe["months"])
            if prior:
                point = _composition(by_month_eon.get(prior, []), by_month_eon.get(month, []))
                point["month"] = month
                composition.append(point)
        return {"data": {"metricId": metric_id, "points": points, "composition": composition}, "warnings": warnings, "asOf": None}

    extra = {"from": month_from, "to": month_to}
    return _run(
        request,
        f"metrics/{metric_id}/trend",
        {**scope.cache_params(), **extra},
        scope,
        produce,
        _no_fallback,
        validate_month=False,
    )


def breakdowns(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, _SCOPE | {"dimension", "level", "parent", "sort", "page", "pageSize"})
    dimension = one(params, "dimension")
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise validation("dimension is required and must be an allowed breakdown.", field="dimension")
    level = 1
    parent = None
    if dimension == "org":
        from app.portfolio.scope import parse_level, parse_parent
        level = parse_level(params)
        parent = parse_parent(params, level=level)
    elif one(params, "parent"):
        raise validation("parent is only valid when dimension is org.", field="parent")
    sort_field, direction = parse_sort(one(params, "sort"), BREAK_SORT, ("nonCompliant", "desc"))
    page, page_size = parse_page(params)

    def produce(connection, probe, catalog, resolved):
        _require_metric(connection, catalog, metric_id)
        if parent and parent not in catalog["trees"][resolved.org_tree]["level1"]:
            raise validation("parent is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="parent", field_code="UNKNOWN_FILTER_VALUE")
        month = resolved.resolved_month
        prior = prior_in_index(month, probe["months"])
        months = [month] + ([prior] if prior else [])
        rows = repository.metric_breakdown(connection, resolved, metric_id, months, dimension, level, parent)
        current = [row for row in rows if row["MONTH_END"] == month]
        previous = {}
        if prior:
            previous = {str(row["ITEM_KEY"]): row for row in rows if row["MONTH_END"] == prior}
        total_nc = sum(int(row["NON_COMPLIANT"] or 0) for row in current)
        items = []
        for row in current:
            key = "" if row["ITEM_KEY"] is None else str(row["ITEM_KEY"])
            label = key if row["ITEM_LABEL"] is None else str(row["ITEM_LABEL"])
            prior_row = previous.get(key)
            items.append({
                "key": key,
                "label": label,
                "applications": int(row["APPLICATIONS"] or 0),
                "nonCompliantApplications": int(row["NON_COMPLIANT"] or 0),
                "rate": rate_value(
                    row["NUMERATOR"],
                    row["DENOMINATOR"],
                    None if prior_row is None else prior_row["NUMERATOR"],
                    None if prior_row is None else prior_row["DENOMINATOR"],
                ),
                "shareOfMetricNonCompliant": share(int(row["NON_COMPLIANT"] or 0), total_nc),
            })
        getters = {
            "applications": lambda item: item["applications"],
            "nonCompliant": lambda item: item["nonCompliantApplications"],
            "rate": lambda item: item["rate"]["rate"],
            "key": lambda item: item["key"],
        }
        items = sort_by(items, getters[sort_field], direction == "desc", lambda item: item["key"])
        page_items, page_block = paginate(items, page, page_size)
        data = {
            "metricId": metric_id,
            "month": month,
            "dimension": dimension,
            "items": page_items,
            "page": page_block,
        }
        if dimension == "org":
            data["orgTree"] = resolved.org_tree
            data["level"] = level
        return {"data": data, "warnings": warnings, "asOf": month}

    extra = {"dimension": dimension, "level": level, "parent": parent, "sort": f"{sort_field}:{direction}", "page": page, "pageSize": page_size}
    return _run(request, f"metrics/{metric_id}/breakdowns", {**scope.cache_params(), **extra}, scope, produce, _no_fallback)


def metric_applications(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, _SCOPE | {"status", "testStatus", "reason", "q", "sort", "page", "pageSize"})
    statuses = parse_repeat(params, "status", set(COMPLIANCE_STATUS))
    test_statuses = parse_repeat(params, "testStatus", set(TEST_STATUS))
    reason_tokens = parse_repeat(params, "reason", None)
    sort_field, direction = parse_sort(one(params, "sort"), METRIC_APP_SORT, ("status", "asc"))
    page, page_size = parse_page(params)
    query = parse_q(params)

    def produce(connection, probe, catalog, resolved):
        _require_metric(connection, catalog, metric_id)
        if any(value not in set(catalog["complianceReason"]) for value in reason_tokens):
            raise validation("reason is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="reason", field_code="UNKNOWN_FILTER_VALUE")
        reasons = reason_tokens
        month = resolved.resolved_month
        prior = prior_in_index(month, probe["months"])
        rows = repository.metric_application_rows(connection, resolved, metric_id, month, prior)
        items = [_application_row(row, resolved.org_tree) for row in rows]
        if statuses:
            items = [item for item in items if item["complianceStatus"] in statuses]
        if test_statuses:
            items = [item for item in items if item["testStatus"] in test_statuses]
        if reasons:
            items = [item for item in items if item["complianceReason"] in reasons]
        if query:
            needle = query.upper()
            items = [item for item in items if item["eonId"].upper().startswith(needle) or needle in (item["applicationName"] or "").upper()]
        items = _sort_applications(items, sort_field, direction)
        page_items, page_block = paginate(items, page, page_size)
        return {"data": {"metricId": metric_id, "month": month, "items": page_items, "page": page_block}, "warnings": warnings, "asOf": month}

    extra = {
        "status": list(statuses),
        "testStatus": list(test_statuses),
        "reason": list(reason_tokens),
        "q": query,
        "sort": f"{sort_field}:{direction}",
        "page": page,
        "pageSize": page_size,
    }
    return _run(request, f"metrics/{metric_id}/applications", {**scope.cache_params(), **extra}, scope, produce, _no_fallback)


def load_metric_context(connection, probe, catalog, resolved, metric_id: str) -> dict:
    meta = _require_metric(connection, catalog, metric_id)
    month = resolved.resolved_month
    prior = prior_in_index(month, probe["months"])
    months = _group(repository.metric_month_aggregates(connection, resolved, metric_id)).get(metric_id, {})
    current = months.get(month) or {}
    previous = months.get(prior) if prior else None
    movement_rows = repository.metric_movements(connection, resolved, month, prior, metric_id) if prior else None
    reporting = repository.app_month_totals(connection, resolved, [month])
    reporting_count = int(reporting[0]["APPLICATIONS_REPORTING"] or 0) if reporting else 0
    return {
        "meta": meta,
        "month": month,
        "prior": prior,
        "current": current,
        "previous": previous,
        "movement": None if prior is None else metric_movement_counts(movement_rows),
        "reporting": reporting_count,
        "months": months,
    }


def _preview_payload(connection, probe, catalog, resolved, metric_id, warnings, *, summary: bool):
    ctx = load_metric_context(connection, probe, catalog, resolved, metric_id)
    current = ctx["current"]
    previous = ctx["previous"]
    applications = int(current.get("APPLICATIONS") or 0)
    preview = {
        "metricId": metric_id,
        "family": None,
        "month": ctx["month"],
        "previousMonth": ctx["prior"],
        "rate": rate_value(
            current.get("NUMERATOR"),
            current.get("DENOMINATOR"),
            None if previous is None else previous.get("NUMERATOR"),
            None if previous is None else previous.get("DENOMINATOR"),
        ),
        "movement": ctx["movement"],
        "compliance": compliance_counts(current),
        "testing": {
            **test_counts(current),
            "pass": int(current.get("RESULT_PASS") or 0),
            "fail": int(current.get("RESULT_FAIL") or 0),
            "resultNotRecorded": int(current.get("RESULT_MISSING") or 0),
        },
        "coverage": {
            "applications": applications,
            "applicationsReportingInScope": ctx["reporting"],
            "coverageShare": share(applications, ctx["reporting"]),
            "firstObserved": min(ctx["months"]) if ctx["months"] else ctx["meta"].get("firstMonth"),
            "lastObserved": max(ctx["months"]) if ctx["months"] else ctx["meta"].get("lastMonth"),
            "monthsObserved": len(ctx["months"]),
        },
        "activeFilters": resolved.active(),
        "definition": {
            "summary": get("PD-01")["definition"],
            "denominatorScope": ctx["meta"]["denominatorScope"],
            "numeratorRule": NUMERATOR_RULE,
            "denominatorRule": DENOMINATOR_RULE,
            "definitionIds": ["PD-01", "PD-02", "PD-13", "PD-19"],
        },
        "flags": metric_flags(
            int(current.get("DENOMINATOR") or 0),
            None if ctx["prior"] is None else int((previous or {}).get("APPLICATIONS") or 0),
            no_rows=applications == 0,
        ),
        "links": metric_links(metric_id, ctx["month"]),
        "rag": classify_rate(provisional_rate(int(current.get("NUMERATOR") or 0), int(current.get("DENOMINATOR") or 0))),
    }
    return {"data": preview, "warnings": warnings, "asOf": ctx["month"], "lineage": lineage.rate()}


def _register_item(metric_id, meta, months, month, prior, spine, movement_rows):
    current = months[month]
    previous = months.get(prior) if prior else None
    return {
        "metricId": metric_id,
        "family": None,
        "denominatorScope": meta["denominatorScope"],
        "applications": int(current["APPLICATIONS"] or 0),
        "rate": rate_value(
            current["NUMERATOR"],
            current["DENOMINATOR"],
            None if previous is None else previous["NUMERATOR"],
            None if previous is None else previous["DENOMINATOR"],
        ),
        "complianceRows": compliance_counts(current),
        "nonCompliantApplications": int(current["NON_COMPLIANT"] or 0),
        "testRows": test_counts(current),
        "movement": None if prior is None else metric_movement_counts(movement_rows or []),
        "rag": classify_rate(
            provisional_rate(int(current["NUMERATOR"] or 0), int(current["DENOMINATOR"] or 0))
        ),
        "sparkline": [
            {
                "month": item,
                "rate": None
                if item not in months
                else provisional_rate(int(months[item]["NUMERATOR"] or 0), int(months[item]["DENOMINATOR"] or 0)),
            }
            for item in spine
        ],
    }


def _application_row(row: dict, tree: str) -> dict:
    return {
        "eonId": row["EON_ID"],
        "applicationName": row.get("APPLICATION_NAME"),
        "org": application_org(row, tree),
        "legalEntityCode": row.get("LEGAL_ENTITY_CODE"),
        "complianceStatus": row.get("COMPLIANCE_STATUS"),
        "complianceReason": row.get("COMPLIANCE_REASON"),
        "testStatus": row.get("TEST_STATUS"),
        "testResult": row.get("TEST_RESULT"),
        "isNumerator": int(row.get("IS_NUMERATOR") or 0) == 1,
        "isDenominator": int(row.get("IS_DENOMINATOR") or 0) == 1,
        "rfb": None if row.get("RFB") is None else int(row["RFB"]),
        "openFindings": None if row.get("OPEN_FINDINGS") is None else int(row["OPEN_FINDINGS"]),
        "metricMovement": metric_movement(row.get("COMPLIANCE_STATUS"), row.get("PRIOR_STATUS")),
    }


def _composition(prior_rows: list, current_rows: list) -> dict:
    prior = {row["EON_ID"]: row for row in prior_rows}
    current = {row["EON_ID"]: row for row in current_rows}
    both = set(prior) & set(current)

    def rate_of(ids, source):
        if not ids:
            return None
        numer = sum(int(source[item]["IS_NUMERATOR"] or 0) for item in ids)
        denom = sum(int(source[item]["IS_DENOMINATOR"] or 0) for item in ids)
        return provisional_rate(numer, denom)

    return {
        "continuing": len(both),
        "entered": len(set(current) - set(prior)),
        "left": len(set(prior) - set(current)),
        "continuingRate": rate_of(both, current),
        "priorContinuingRate": rate_of(both, prior),
    }


def _require_metric(connection, catalog, metric_id: str) -> dict:
    found = catalog["metrics"].get(metric_id) if catalog else None
    if found:
        return found
    if not repository.metric_exists(connection, metric_id):
        raise not_found("METRIC_NOT_FOUND", "Metric was not found.")
    scope_name = repository.denominator_for(connection, metric_id)
    return {"metricId": metric_id, "denominatorScope": scope_name or classify_denominator(0, 0), "firstMonth": None, "lastMonth": None, "rows": 0}


def _group(rows: list[dict]) -> dict:
    grouped: dict[str, dict] = {}
    for row in rows:
        grouped.setdefault(row["METRIC_ID"], {})[row["MONTH_END"]] = row
    return grouped


def _shares(pairs, total: int) -> list[dict]:
    return [{"key": key, "rows": value, "share": share(value, total)} for key, value in pairs]


def _sort_register(items, field, direction):
    getters = {
        "metricId": lambda item: item["metricId"],
        "applications": lambda item: item["applications"],
        "nonCompliant": lambda item: item["nonCompliantApplications"],
        "rate": lambda item: item["rate"]["rate"],
        "rateDelta": lambda item: item["rate"]["deltaPp"],
        "rag": lambda item: RAG_RANK.get(item["rag"], 0),
    }
    return sort_by(items, getters[field], direction == "desc", lambda item: item["metricId"])


def _sort_applications(items, field, direction):
    if field == "status":
        def key(item):
            findings = item["openFindings"]
            findings_key = (1, 0) if findings is None else (0, -int(findings))
            rank = _STATUS_RANK.get(item["complianceStatus"], 9)
            if direction == "desc":
                rank = -rank
            return (rank, findings_key, item["eonId"])
        return sorted(items, key=key)
    getters = {
        "name": lambda item: item["applicationName"] or "",
        "rfb": lambda item: item["rfb"],
        "openFindings": lambda item: item["openFindings"],
    }
    return sort_by(items, getters[field], direction == "desc", lambda item: item["eonId"])


def _no_fallback():
    from app.portfolio.services.dashboard import _unsupported
    _unsupported()
