"""Dashboard, filters, definitions and application-list endpoints."""

from __future__ import annotations

from dataclasses import replace

from app.common.v2_errors import unavailable
from app.portfolio import fallback, lineage, repository, runtime
from app.portfolio.definitions import DEFINITIONS_VERSION, POPULATION_NOTE, public_definitions, share
from app.portfolio.month import prior_in_index
from app.portfolio.scope import (
    APP_SORT,
    DISTRIBUTION_DIMENSIONS,
    ORG_SORT,
    SCOPE_KEYS,
    ensure_month,
    one,
    parse_choice,
    parse_level,
    parse_optional_month,
    parse_page,
    parse_parent,
    parse_q,
    parse_scope,
    parse_sort,
    query_lists,
    reject_own_filter,
    unknown_warnings,
)
from app.portfolio.support import count_value, movement_block, org_ref, paginate, share_value, sort_by, zeros

_SCOPE = set(SCOPE_KEYS)


def agent_status() -> dict:
    """Same availability the agent catalogue reports. A portfolio read does not change it."""
    provider = getattr(agent_status, "provider", None)
    if provider is not None:
        value = provider()
        if isinstance(value, str):
            return {"analysis": value, "data": value}
        return value
    from app.common.agent_availability import current

    status = current()
    return {"analysis": status, "data": status}


def status(request):
    params = query_lists(request)
    warnings = unknown_warnings(params, set())

    def produce(connection, probe, catalog, resolved):
        return {
            "data": {
                "latestMonth": probe["latestMonth"],
                "months": len(probe["months"]),
                "dataset": _dataset(probe),
                "source": "snowflake",
                "definitionsVersion": DEFINITIONS_VERSION,
                "agents": agent_status(),
            },
            "warnings": warnings,
            "asOf": None,
        }

    def fallback_fn():
        if not fallback.available():
            raise unavailable("Snowflake did not answer.")
        data = fallback.status_data()
        data["agents"] = agent_status()
        return {"data": data, "warnings": warnings + fallback.warnings(), "asOf": None}

    return runtime.execute(
        request,
        endpoint="status",
        params={"unknown": _unknown(params, set())},
        ttl=60,
        produce=produce,
        fallback_fn=fallback_fn,
        require_catalog=False,
        dependency="unavailable",
    )


def filters(request):
    params = query_lists(request)
    warnings = unknown_warnings(params, set())

    def produce(connection, probe, catalog, resolved):
        latest = probe["latestMonth"]
        return {
            "data": {
                "defaultMonth": latest,
                "months": [
                    {**row, "isLatest": row["month"] == latest}
                    for row in catalog["months"]
                ],
                "orgTrees": {
                    "BUSINESS_ORG": _tree(catalog["trees"]["BUSINESS_ORG"], "Super division", "Division"),
                    "BU": _tree(catalog["trees"]["BU"], "BU super division", "BU division"),
                },
                "legalEntities": catalog["legal"],
                "tiers": catalog["tiers"],
                "risks": catalog["risks"],
                "lifecycles": catalog["lifecycles"],
                "maOptions": ["Y", "N"],
                "vocab": {
                    "complianceStatus": catalog["complianceStatus"],
                    "testStatus": catalog["testStatus"],
                    "testResult": catalog["testResult"],
                    "complianceReason": catalog["complianceReason"],
                    "movement": catalog["movement"],
                },
                "metrics": [
                    {
                        "metricId": item["metricId"],
                        "rows": item["rows"],
                        "firstMonth": item["firstMonth"],
                        "lastMonth": item["lastMonth"],
                        "denominatorScope": item["denominatorScope"],
                    }
                    for item in sorted(catalog["metrics"].values(), key=lambda item: item["metricId"])
                ],
            },
            "warnings": warnings,
            "asOf": None,
        }

    return runtime.execute(
        request,
        endpoint="filters",
        params={"unknown": _unknown(params, set())},
        ttl=600,
        produce=produce,
        fallback_fn=None,
        require_catalog=True,
        dependency="unavailable",
    )


def definitions(request):
    params = query_lists(request)
    warnings = unknown_warnings(params, set())

    def produce(connection, probe, catalog, resolved):
        return {"data": public_definitions(), "warnings": warnings, "asOf": None}

    def fallback_fn():
        return {
            "data": public_definitions(),
            "warnings": warnings + [{
                "code": "DATASET_UNVERIFIED",
                "message": "Definitions are served from the registry. The dataset probe did not answer.",
            }],
            "asOf": None,
        }

    return runtime.execute(
        request,
        endpoint="definitions",
        params={"unknown": _unknown(params, set())},
        ttl=3600,
        produce=produce,
        fallback_fn=fallback_fn,
        require_catalog=False,
        dependency="unavailable",
    )


def overview(request):
    params, scope, warnings = _scoped(request, _SCOPE)

    def produce(connection, probe, catalog, resolved):
        prior = prior_in_index(resolved.resolved_month, probe["months"])
        months = [resolved.resolved_month] + ([prior] if prior else [])
        rows = {row["MONTH_END"]: row for row in repository.app_month_totals(connection, resolved, months)}
        current = rows.get(resolved.resolved_month) or zeros()
        previous = None if prior is None else rows.get(prior) or zeros()
        snap = repository.snapshot(connection, resolved.resolved_month)
        return {
            "data": _overview(resolved.resolved_month, prior, current, previous, snap, probe),
            "warnings": warnings,
            "asOf": resolved.resolved_month,
            "lineage": lineage.overview(),
        }

    def fallback_fn():
        _require_packaged(scope)
        return {
            "data": fallback.overview_data(),
            "warnings": warnings + fallback.warnings(),
            "asOf": fallback.latest_month(),
            "lineage": lineage.overview(),
        }

    return _run(request, "overview", params, scope, produce, fallback_fn, lineage=lineage.overview())


def trends(request):
    params, scope, warnings = _scoped(request, _SCOPE | {"from", "to"})
    month_from = parse_optional_month(params, "from")
    month_to = parse_optional_month(params, "to")

    def produce(connection, probe, catalog, resolved):
        if month_from:
            ensure_month(month_from, probe["months"])
        if month_to:
            ensure_month(month_to, probe["months"])
        rows = {row["MONTH_END"]: row for row in repository.app_month_totals(connection, resolved, None)}
        first = probe["months"][0] if probe["months"] else None
        points = []
        for month in probe["months"]:
            if month_from and month < month_from:
                continue
            if month_to and month > month_to:
                continue
            row = rows.get(month) or zeros()
            apps = int(row["APPLICATIONS_REPORTING"] or 0)
            nc = int(row["NON_COMPLIANT"] or 0)
            opening = month == first
            points.append({
                "month": month,
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": share(nc, apps),
                "withoutCompletedTest": int(row["NO_TEST"] or 0),
                "withFailedTest": int(row["FAILED"] or 0),
                "newlyNonCompliant": None if opening else int(row["NEWLY"] or 0),
                "resolved": None if opening else int(row["RESOLVED"] or 0),
                "persistentNonCompliant": None if opening else int(row["PERSISTENT"] or 0),
                "metricRows": int(row["METRIC_ROWS"] or 0),
                "openFindings": int(row["OPEN_FINDINGS"] or 0),
            })
        return {"data": {"points": points, "note": dict(POPULATION_NOTE)}, "warnings": warnings, "asOf": None}

    def fallback_fn():
        _require_packaged(scope, ignore_month=True)
        if month_from or month_to:
            raise _unsupported()
        return {"data": fallback.trends_data(None, None), "warnings": warnings + fallback.warnings(), "asOf": None}

    extra = {"from": month_from, "to": month_to}
    return _run(request, "trends", {**_cache_scope(scope), **extra}, scope, produce, fallback_fn, validate_month=False)


def compliance(request):
    params, scope, warnings = _scoped(request, _SCOPE | {"include"})
    include = one(params, "include")
    if include not in {None, "", "precedence"}:
        from app.common.v2_errors import validation
        raise validation("include must be precedence.", field="include")

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        counts = {row["STATUS"]: int(row["ROWS"] or 0) for row in repository.metric_status_counts(connection, resolved, month)}
        order = ["Compliant", "Non_Compliant", "Pending", "Not_Applicable"]
        keys = order + sorted(key for key in counts if key not in order)
        total = sum(counts.values())
        by_status = []
        for key in keys:
            rows = counts.get(key, 0)
            if key not in order and rows == 0:
                continue
            by_status.append({"status": key, "rows": rows, "share": share(rows, total)})
        totals = {row["MONTH_END"]: row for row in repository.app_month_totals(connection, resolved, [month])}
        current = totals.get(month) or zeros()
        apps = int(current["APPLICATIONS_REPORTING"] or 0)
        nc = int(current["NON_COMPLIANT"] or 0)
        applications = {"nonCompliant": nc, "notNonCompliant": apps - nc, "total": apps}
        if include == "precedence":
            found = {row["STATUS"]: int(row["APPLICATIONS"] or 0) for row in repository.status_precedence(connection, resolved, month)}
            applications["statusPrecedence"] = [
                {"status": name, "applications": found.get(name, 0), "definitionId": "PD-09"}
                for name in ("NON_COMPLIANT", "PENDING", "COMPLIANT", "NOT_APPLICABLE")
            ]
        reasons = [
            {
                "reason": row["REASON"],
                "rows": int(row["ROWS"] or 0),
                "nonCompliantRows": int(row["NON_COMPLIANT_ROWS"] or 0),
            }
            for row in repository.top_reasons(connection, resolved, month)
        ]
        return {
            "data": {"month": month, "metricRows": {"total": total, "byStatus": by_status}, "applications": applications, "topReasons": reasons},
            "warnings": warnings,
            "asOf": month,
        }

    return _run(request, "distributions/compliance", {**_cache_scope(scope), "include": include}, scope, produce, _unsupported)


def testing(request):
    params, scope, warnings = _scoped(request, _SCOPE | {"series"})
    from app.portfolio.scope import parse_bool
    series = parse_bool(params, "series", default=False)
    order = ["Test_Complete", "No_Test", "Test_Pending", "Exempt"]

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        by_status, results = repository.test_distribution(connection, resolved, month)
        found = {row["TEST_STATUS"]: row for row in by_status}
        total = sum(int(row["ROWS"] or 0) for row in by_status)
        statuses = []
        keys = order + sorted(key for key in found if key not in order)
        for key in keys:
            row = found.get(key)
            rows = int(row["ROWS"] or 0) if row else 0
            if key not in order and rows == 0:
                continue
            statuses.append({
                "testStatus": key,
                "metricRows": rows,
                "share": share(rows, total),
                "distinctApplications": int(row["APPS"] or 0) if row else 0,
            })
        totals = {row["MONTH_END"]: row for row in repository.app_month_totals(connection, resolved, None if series else [month])}
        current = totals.get(month) or zeros()
        data = {
            "month": month,
            "byTestStatus": statuses,
            "completedTestResults": {
                "pass": int(results.get("PASS") or 0),
                "fail": int(results.get("FAIL") or 0),
                "notRecorded": int(results.get("NOT_RECORDED") or 0),
            },
            "applications": {
                "withoutCompletedTest": int(current["NO_TEST"] or 0),
                "withFailedTest": int(current["FAILED"] or 0),
                "reporting": int(current["APPLICATIONS_REPORTING"] or 0),
            },
        }
        if series:
            data["series"] = [
                {
                    "month": item,
                    "applicationsReporting": int((totals.get(item) or zeros())["APPLICATIONS_REPORTING"] or 0),
                    "withoutCompletedTest": int((totals.get(item) or zeros())["NO_TEST"] or 0),
                    "withFailedTest": int((totals.get(item) or zeros())["FAILED"] or 0),
                }
                for item in probe["months"]
            ]
        return {"data": data, "warnings": warnings, "asOf": month}

    def fallback_fn():
        _require_packaged(scope)
        note = fallback.partial_warning("Test status and completed-test results are not in the packaged extract.")
        return {"data": fallback.testing_data(series), "warnings": warnings + fallback.warnings(note), "asOf": fallback.latest_month()}

    return _run(request, "distributions/testing", {**_cache_scope(scope), "series": series}, scope, produce, fallback_fn)


def distribution(request, dimension: str):
    if dimension not in DISTRIBUTION_DIMENSIONS:
        from app.common.v2_errors import validation
        raise validation("dimension must be risk, tier, lifecycle, rto or legalEntity.", field="dimension")
    params, scope, warnings = _scoped(request, _SCOPE)
    reject_own_filter(dimension, scope)

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        rows = repository.attribute_distribution(connection, resolved, month, dimension)
        total = sum(int(row["APPLICATIONS_REPORTING"] or 0) for row in rows)
        items = []
        for row in rows:
            apps = int(row["APPLICATIONS_REPORTING"] or 0)
            nc = int(row["NON_COMPLIANT"] or 0)
            key = "" if row["ITEM_KEY"] is None else str(row["ITEM_KEY"])
            label = key if row["ITEM_LABEL"] is None else str(row["ITEM_LABEL"])
            items.append({
                "key": key,
                "label": label,
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": share(nc, apps),
                "share": share(apps, total),
            })
        items.sort(key=lambda item: item["key"])
        return {
            "data": {"month": month, "dimension": dimension, "items": items, "definitionIds": ["PD-08", "PD-11"]},
            "warnings": warnings,
            "asOf": month,
        }

    def fallback_fn():
        if dimension != "risk":
            raise _unsupported()
        _require_packaged(scope)
        return {"data": fallback.risk_data(), "warnings": warnings + fallback.warnings(), "asOf": fallback.latest_month()}

    return _run(request, f"distributions/{dimension}", {**_cache_scope(scope), "dimension": dimension}, scope, produce, fallback_fn)


def org_contribution(request):
    params = query_lists(request)
    allowed = _SCOPE | {"level", "parent", "sort", "page", "pageSize"}
    warnings = unknown_warnings(params, allowed)
    scope = parse_scope(params)
    if scope.l1 or scope.l2:
        warnings = warnings + [{
            "code": "UNKNOWN_PARAMETER",
            "message": "Ignored l1 and l2 on organisation contribution. Use level and parent.",
        }]
        scope = replace(scope, l1=(), l2=())
    level = parse_level(params)
    parent = parse_parent(params, level=level)
    sort_field, direction = parse_sort(one(params, "sort"), ORG_SORT, ("nonCompliant", "desc"))
    page, page_size = parse_page(params, default_size=50)

    def produce(connection, probe, catalog, resolved):
        if parent and parent not in catalog["trees"][resolved.org_tree]["level1"]:
            from app.common.v2_errors import validation
            raise validation("parent is not an allowed value.", code="UNKNOWN_FILTER_VALUE", field="parent", field_code="UNKNOWN_FILTER_VALUE")
        month = resolved.resolved_month
        prior = prior_in_index(month, probe["months"])
        rows = repository.org_groups(connection, resolved, month, level, parent)
        items = []
        for row in rows:
            apps = int(row["APPLICATIONS_REPORTING"] or 0)
            nc = int(row["NON_COMPLIANT"] or 0)
            level1 = row.get("LEVEL1")
            level2 = row.get("LEVEL2")
            key = level1 if level == 1 else level2
            items.append({
                "key": key,
                "label": key,
                "org": org_ref(resolved.org_tree, level1, None if level == 1 else level2),
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": share(nc, apps),
                "contributionShare": None,
                "newlyNonCompliant": None if prior is None else int(row["NEWLY"] or 0),
                "resolved": None if prior is None else int(row["RESOLVED"] or 0),
                "withoutCompletedTest": int(row["NO_TEST"] or 0),
                "withFailedTest": int(row["FAILED"] or 0),
                "openFindings": int(row["OPEN_FINDINGS"] or 0),
            })
        total_apps = sum(item["applicationsReporting"] for item in items)
        total_nc = sum(item["nonCompliantApplications"] for item in items)
        for item in items:
            item["contributionShare"] = share(item["nonCompliantApplications"], total_nc)
        getters = {
            "nonCompliant": lambda item: item["nonCompliantApplications"],
            "share": lambda item: item["nonCompliantShare"],
            "reporting": lambda item: item["applicationsReporting"],
            "openFindings": lambda item: item["openFindings"],
            "name": lambda item: item["label"] or "",
        }
        items = sort_by(items, getters[sort_field], direction == "desc", lambda item: item["label"] or "")
        page_items, page_block = paginate(items, page, page_size)
        return {
            "data": {
                "month": month,
                "orgTree": resolved.org_tree,
                "level": level,
                "parent": parent,
                "totals": {"applicationsReporting": total_apps, "nonCompliantApplications": total_nc},
                "items": page_items,
                "page": page_block,
            },
            "warnings": warnings,
            "asOf": month,
        }

    def fallback_fn():
        if scope.org_tree != "BUSINESS_ORG":
            raise _unsupported()
        _require_packaged(scope)
        note = fallback.partial_warning(
            "Newly non-compliant, resolved and test counts are not in the packaged organisation extract."
        )
        return {
            "data": fallback.org_data(level, parent, sort_field, direction, page, page_size),
            "warnings": warnings + fallback.warnings(note),
            "asOf": fallback.latest_month(),
        }

    extra = {"level": level, "parent": parent, "sort": f"{sort_field}:{direction}", "page": page, "pageSize": page_size}
    return _run(request, "org/contribution", {**_cache_scope(scope), **extra}, scope, produce, fallback_fn)


def data_coverage(request):
    params, scope, warnings = _scoped(request, {"month"})

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        raw = repository.coverage(connection, month)
        snap = repository.snapshot(connection, month)
        population = raw["applicationsInDataset"]
        return {
            "data": {
                "month": month,
                "applicationsInDataset": population,
                "applicationsReporting": raw["applicationsReporting"],
                "applicationsNotReporting": population - raw["applicationsReporting"],
                "observedInAllMonths": {
                    "applications": raw["observedInAllMonths"],
                    "share": share(raw["observedInAllMonths"], population),
                },
                "observedInOneMonthOnly": {
                    "applications": raw["observedInOneMonthOnly"],
                    "share": share(raw["observedInOneMonthOnly"], population),
                },
                "metricsInDataset": raw["metricsInDataset"],
                "metricRowsInDataset": raw["metricRowsInDataset"],
                "applicationMonthsInDataset": raw["applicationMonthsInDataset"],
                "months": {"first": raw["first"], "last": raw["last"], "count": raw["monthCount"]},
                "freshness": {
                    "datasetVersion": snap["version"] if snap else probe["version"],
                    "promotedAt": probe["promotedAt"],
                    "snapshotGeneratedAt": None if snap is None else snap["generatedAt"],
                },
            },
            "warnings": warnings,
            "asOf": month,
        }

    return _run(request, "data-coverage", _cache_scope(scope), scope, produce, _unsupported, require_catalog=False)


def applications(request):
    from app.portfolio.scope import ATTENTION, parse_metric_id

    params, scope, warnings = _scoped(request, _SCOPE | {"attention", "metricId", "q", "sort", "page", "pageSize"})
    attention = parse_choice(params, "attention", ATTENTION)
    metric_id = one(params, "metricId")
    if metric_id:
        metric_id = parse_metric_id(metric_id)
    q = parse_q(params)
    sort_field, direction = parse_sort(one(params, "sort"), APP_SORT, ("openFindings", "desc"))
    page, page_size = parse_page(params)

    def produce(connection, probe, catalog, resolved):
        month = resolved.resolved_month
        rows = repository.application_rows(connection, resolved, month, attention, q, metric_id)
        items = [_application_item(row, resolved.org_tree) for row in rows]
        getters = {
            "name": lambda item: item["applicationName"] or "",
            "openFindings": lambda item: item["openFindings"],
            "metricRows": lambda item: item["metricRows"],
            "org": lambda item: item["org"]["level1"] or "",
        }
        items = sort_by(items, getters[sort_field], direction == "desc", lambda item: item["eonId"])
        counts = {}
        for item in items:
            counts[item["org"]["level1"]] = counts.get(item["org"]["level1"], 0) + 1
        top = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
        page_items, page_block = paginate(items, page, page_size)
        return {
            "data": {
                "month": month,
                "items": page_items,
                "summary": {"matching": len(items), "byOrgLevel1": [{"key": key, "count": count} for key, count in top]},
                "page": page_block,
            },
            "warnings": warnings,
            "asOf": month,
        }

    def fallback_fn():
        if metric_id or scope.org_tree != "BUSINESS_ORG":
            raise _unsupported()
        _require_packaged(scope)
        note = fallback.partial_warning(
            "legalEntityCode, organisation level 2, metricsReported, nonCompliantRows and nonCompliantSince are not in the packaged extract."
        )
        return {
            "data": fallback.applications_data(attention, q, sort_field, direction, page, page_size),
            "warnings": warnings + fallback.warnings(note),
            "asOf": fallback.latest_month(),
        }

    extra = {
        "attention": attention,
        "metricId": metric_id,
        "q": q,
        "sort": f"{sort_field}:{direction}",
        "page": page,
        "pageSize": page_size,
    }
    return _run(request, "applications", {**_cache_scope(scope), **extra}, scope, produce, fallback_fn)


def _application_item(row: dict, tree: str) -> dict:
    from app.portfolio.support import application_org, bool_flag

    return {
        "eonId": row["EON_ID"],
        "applicationName": row["APPLICATION_NAME"],
        "org": application_org(row, tree),
        "legalEntityCode": row.get("LEGAL_ENTITY_CODE"),
        "tier": int(row["APPLICATION_TIER"]),
        "risk": row.get("ASSET_RISK_RATING_2"),
        "lifecycle": row.get("LIFECYCLE_PHASE"),
        "isNonCompliant": bool_flag(row, "IS_NON_COMPLIANT_APP"),
        "hasNoCompletedTest": bool_flag(row, "HAS_NO_COMPLETED_TEST"),
        "hasFailedTest": bool_flag(row, "HAS_FAILED_TEST"),
        "movement": row.get("MOVEMENT_STATUS"),
        "metricsReported": int(row.get("METRICS_REPORTED") or 0),
        "metricRows": int(row.get("METRIC_ROWS") or 0),
        "nonCompliantRows": int(row.get("NON_COMPLIANT_ROWS") or 0),
        "openFindings": None if row.get("OPEN_FINDINGS") is None else int(row["OPEN_FINDINGS"]),
        "nonCompliantSince": row.get("NON_COMPLIANT_SINCE"),
    }


def _overview(month, prior, current, previous, snap, probe) -> dict:
    apps = int(current["APPLICATIONS_REPORTING"] or 0)
    nc = int(current["NON_COMPLIANT"] or 0)
    prior_apps = None if previous is None else int(previous["APPLICATIONS_REPORTING"] or 0)
    prior_nc = None if previous is None else int(previous["NON_COMPLIANT"] or 0)
    return {
        "month": month,
        "previousMonth": prior,
        "applicationsReporting": count_value(apps, prior_apps),
        "nonCompliant": {
            "applications": count_value(nc, prior_nc),
            "share": share_value(nc, apps, prior_nc, prior_apps),
        },
        "testing": {
            "withoutCompletedTest": count_value(current["NO_TEST"], None if previous is None else previous["NO_TEST"]),
            "withFailedTest": count_value(current["FAILED"], None if previous is None else previous["FAILED"]),
        },
        "openFindings": count_value(
            0 if current.get("OPEN_FINDINGS") is None else current["OPEN_FINDINGS"],
            None if previous is None else (0 if previous.get("OPEN_FINDINGS") is None else previous["OPEN_FINDINGS"]),
        ),
        "metricRows": count_value(current["METRIC_ROWS"], None if previous is None else previous["METRIC_ROWS"]),
        "movement": movement_block(current, enabled=prior is not None),
        "freshness": {
            "datasetVersion": snap["version"] if snap else probe["version"],
            "snapshotGeneratedAt": None if snap is None else snap["generatedAt"],
            "sourceRowCount": probe["rowCount"] if snap is None or snap.get("sourceRowCount") is None else snap["sourceRowCount"],
        },
    }


def _tree(node: dict, level1: str, level2: str) -> dict:
    return {
        "level1Label": level1,
        "level2Label": level2,
        "level1": [
            {"value": row["VALUE"], "applications": int(row["APPLICATIONS"] or 0)}
            for row in node["level1Rows"]
        ],
        "level2": [{"value": row["VALUE"], "parent": row["PARENT"]} for row in node["level2Rows"]],
    }


def _dataset(probe) -> dict:
    return {"version": probe["version"], "rowCount": probe["rowCount"], "promotedAt": probe["promotedAt"]}


def _scoped(request, allowed: set[str]):
    params = query_lists(request)
    return params, parse_scope(params), unknown_warnings(params, allowed)


def _cache_scope(scope) -> dict:
    return scope.cache_params()


def _unknown(params, allowed) -> list[str]:
    return sorted(key for key in params if key not in allowed)


def _require_packaged(scope, *, ignore_month: bool = False) -> None:
    if not fallback.eligible(scope, scope.month, ignore_month=ignore_month):
        raise _unsupported()


def _unsupported():
    raise unavailable(
        "This response has no packaged extract for the current request.",
        code="FALLBACK_UNSUPPORTED",
    )


def _run(request, endpoint, params, scope, produce, fallback_fn, *, lineage=None, validate_month=True, require_catalog=True):
    params = {**params, "unknown": _unknown(query_lists(request), set(params) | _SCOPE | {"month"})}
    return runtime.execute(
        request,
        endpoint=endpoint,
        params=params,
        ttl=600,
        produce=produce,
        fallback_fn=fallback_fn,
        scope=scope,
        require_catalog=require_catalog,
        validate_month=validate_month,
        lineage=lineage,
    )
