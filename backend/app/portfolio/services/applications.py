"""Application detail and history."""

from __future__ import annotations

from app.common.v2_errors import not_found
from app.portfolio import repository
from app.portfolio.definitions import HISTORY_NOTE, metric_movement, share, status_precedence
from app.portfolio.month import prior_in_index
from app.portfolio.scope import SCOPE_KEYS, one, parse_bool, parse_eon_id, parse_metric_id
from app.portfolio.services.dashboard import _run, _scoped, _unsupported
from app.portfolio.support import application_org, bool_flag, nc_since

_FIELDS = (
    ("tier", "APPLICATION_TIER"),
    ("risk", "ASSET_RISK_RATING_2"),
    ("lifecycle", "LIFECYCLE_PHASE"),
    ("rto", "APPLICATION_RTO"),
    ("legalEntityCode", "LEGAL_ENTITY_CODE"),
    ("legalEntityName", "LEGAL_ENTITY_NAME"),
    ("isMergersAcquisitionsAsset", "IS_MERGERS_ACQUISITIONS_ASSET"),
    ("businessOrg.level1", "SUPER_DIVISION"),
    ("businessOrg.level2", "DIVISION"),
    ("businessOrg.superDepartment", "SUPER_DEPARTMENT"),
    ("businessOrg.department", "DEPARTMENT"),
    ("businessOrg.busOrgLgNm", "BUS_ORG_LG_NM"),
    ("bu.level1", "BU_SUPER_DIVISION"),
    ("bu.level2", "BU_DIVISION"),
    ("bu.buSuperDepartment", "BU_SUPER_DEPARTMENT"),
    ("bu.buDepartment", "BU_DEPARTMENT"),
)


def detail(request, eon_id: str):
    eon_id = parse_eon_id(eon_id)
    params, scope, warnings = _scoped(request, {"month", "includeOwners"})
    include_owners = parse_bool(params, "includeOwners", default=False)

    def produce(connection, probe, catalog, resolved):
        payload = build_detail(connection, probe, eon_id, scope.month, include_owners)
        payload["warnings"] = warnings + payload["warnings"]
        return payload

    return _run(
        request,
        f"applications/{eon_id}",
        {"includeOwners": include_owners, **scope.cache_params()},
        scope,
        produce,
        _unsupported,
        require_catalog=False,
    )


def history(request, eon_id: str):
    eon_id = parse_eon_id(eon_id)
    params, scope, warnings = _scoped(request, {"metricId"})
    metric_id = one(params, "metricId")
    if metric_id:
        metric_id = parse_metric_id(metric_id)

    def produce(connection, probe, catalog, resolved):
        payload = build_history(connection, probe, eon_id, metric_id)
        payload["warnings"] = warnings + payload["warnings"]
        return payload

    return _run(
        request,
        f"applications/{eon_id}/history",
        {"metricId": metric_id},
        scope,
        produce,
        _unsupported,
        require_catalog=False,
        validate_month=False,
    )


def build_detail(connection, probe, eon_id: str, month: str | None, include_owners: bool) -> dict:
    rows = repository.application_months(connection, eon_id)
    if not rows:
        raise not_found("APPLICATION_NOT_FOUND", "Application was not found.")
    by_month = {row["MONTH_END"]: row for row in rows}
    last = rows[-1]
    month = month or last["MONTH_END"]
    current = by_month.get(month)
    observed = current is not None
    source = current or last
    warnings = []
    if not observed:
        warnings.append({
            "code": "NOT_OBSERVED",
            "message": "The application did not report in the requested month.",
        })
    all_metric_rows = repository.application_metric_rows(connection, eon_id) if observed else []
    metric_rows = [row for row in all_metric_rows if row["MONTH_END"] == month]
    prior_metric = {}
    prior_month = prior_in_index(month, probe["months"])
    if observed and prior_month:
        for row in all_metric_rows:
            if row["MONTH_END"] == prior_month:
                prior_metric[row["METRIC_ID"]] = row.get("COMPLIANCE_STATUS")
    previous = _previous_observed(rows, month if observed else source["MONTH_END"])
    changes = _changes(previous, source, source["MONTH_END"]) if previous and observed else []
    peers = _peers(connection, month if observed else source["MONTH_END"], source)
    return {
        "data": _detail_body(eon_id, month, observed, last["MONTH_END"], source, metric_rows, prior_metric, changes, peers, include_owners),
        "warnings": warnings,
        "asOf": month,
    }


def build_history(connection, probe, eon_id: str, metric_id: str | None) -> dict:
    rows = repository.application_months(connection, eon_id)
    if not rows:
        raise not_found("APPLICATION_NOT_FOUND", "Application was not found.")
    by_month = {row["MONTH_END"]: row for row in rows}
    months = []
    for month in probe["months"]:
        row = by_month.get(month)
        if row is None:
            months.append({"month": month, "observed": False})
        else:
            months.append({
                "month": month,
                "observed": True,
                "isNonCompliant": bool_flag(row, "IS_NON_COMPLIANT_APP"),
                "hasNoCompletedTest": bool_flag(row, "HAS_NO_COMPLETED_TEST"),
                "hasFailedTest": bool_flag(row, "HAS_FAILED_TEST"),
                "movement": row.get("MOVEMENT_STATUS"),
                "metricsReported": int(row.get("METRICS_REPORTED") or 0),
                "metricRows": int(row.get("METRIC_ROWS") or 0),
                "openFindings": None if row.get("OPEN_FINDINGS") is None else int(row["OPEN_FINDINGS"]),
            })
    metric_rows = repository.application_metric_rows(connection, eon_id)
    grouped: dict[str, dict] = {}
    for row in metric_rows:
        grouped.setdefault(row["METRIC_ID"], {})[row["MONTH_END"]] = row
    if metric_id:
        ids = [metric_id]
    else:
        ids = sorted(grouped)
    timeline = []
    for item_id in ids:
        points = []
        present = grouped.get(item_id, {})
        for month in probe["months"]:
            row = present.get(month)
            if row is None:
                points.append({"month": month, "observed": False})
            else:
                points.append({
                    "month": month,
                    "observed": True,
                    "complianceStatus": row.get("COMPLIANCE_STATUS"),
                    "testStatus": row.get("TEST_STATUS"),
                    "testResult": row.get("TEST_RESULT"),
                })
        timeline.append({"metricId": item_id, "months": points})
    changes = []
    observed_rows = [row for row in rows]
    for index, row in enumerate(observed_rows):
        if index == 0:
            continue
        changes.extend(_changes(observed_rows[index - 1], row, row["MONTH_END"]))
    return {
        "data": {
            "eonId": eon_id,
            "window": {"first": probe["months"][0], "last": probe["months"][-1]} if probe["months"] else {"first": None, "last": None},
            "months": months,
            "metricTimeline": timeline,
            "attributeChanges": changes,
            "note": HISTORY_NOTE,
        },
        "warnings": [],
        "asOf": None,
    }


def observed_map(rows: list[dict]) -> dict[str, bool]:
    return {row["MONTH_END"]: bool_flag(row, "IS_NON_COMPLIANT_APP") for row in rows}


def non_compliant_since(rows: list[dict], month: str, first_month: str):
    return nc_since(observed_map(rows), month, first_month)


def _detail_body(eon_id, month, observed, last_month, source, metric_rows, prior_metric, changes, peers, include_owners):
    compliant = sum(1 for row in metric_rows if row.get("COMPLIANCE_STATUS") == "Compliant")
    non_compliant = sum(1 for row in metric_rows if row.get("COMPLIANCE_STATUS") == "Non_Compliant")
    pending = sum(1 for row in metric_rows if row.get("COMPLIANCE_STATUS") == "Pending")
    status = {
        "isNonCompliant": bool_flag(source, "IS_NON_COMPLIANT_APP") if observed else False,
        "hasNoCompletedTest": bool_flag(source, "HAS_NO_COMPLETED_TEST") if observed else False,
        "hasFailedTest": bool_flag(source, "HAS_FAILED_TEST") if observed else False,
        "movement": source.get("MOVEMENT_STATUS") if observed else "NO_PRIOR_MONTH",
        "metricsReported": int(source.get("METRICS_REPORTED") or 0) if observed else 0,
        "metricRows": int(source.get("METRIC_ROWS") or 0) if observed else 0,
        "nonCompliantRows": int(source.get("NON_COMPLIANT_ROWS") or 0) if observed else 0,
        "openFindings": None if not observed or source.get("OPEN_FINDINGS") is None else int(source["OPEN_FINDINGS"]),
        "statusPrecedence": status_precedence(compliant, non_compliant, pending) if observed else "NOT_APPLICABLE",
    }
    metrics = []
    for row in metric_rows:
        metrics.append({
            "metricId": row["METRIC_ID"],
            "complianceStatus": row.get("COMPLIANCE_STATUS"),
            "complianceReason": row.get("COMPLIANCE_REASON"),
            "testStatus": row.get("TEST_STATUS"),
            "testResult": row.get("TEST_RESULT"),
            "isNumerator": int(row.get("IS_NUMERATOR") or 0) == 1,
            "isDenominator": int(row.get("IS_DENOMINATOR") or 0) == 1,
            "rfb": None if row.get("RFB") is None else int(row["RFB"]),
            "metricMovement": metric_movement(row.get("COMPLIANCE_STATUS"), prior_metric.get(row["METRIC_ID"])),
        })
    return {
        "eonId": eon_id,
        "applicationName": source.get("APPLICATION_NAME"),
        "month": month,
        "observed": observed,
        "lastObservedMonth": last_month,
        "attributes": _attributes(source, include_owners),
        "changedAttributes": changes,
        "status": status,
        "metrics": metrics,
        "peers": peers,
    }


def _attributes(row: dict, include_owners: bool) -> dict:
    owners = None
    if include_owners:
        owners = {
            "business": _person(row, "PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"),
            "it": _person(row, "PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME"),
        }
    return {
        "tier": int(row["APPLICATION_TIER"]) if row.get("APPLICATION_TIER") is not None else None,
        "risk": row.get("ASSET_RISK_RATING_2"),
        "lifecycle": row.get("LIFECYCLE_PHASE"),
        "rto": row.get("APPLICATION_RTO"),
        "legalEntityCode": row.get("LEGAL_ENTITY_CODE"),
        "legalEntityName": row.get("LEGAL_ENTITY_NAME"),
        "isMergersAcquisitionsAsset": str(row.get("IS_MERGERS_ACQUISITIONS_ASSET") or "") == "Y",
        "org": {
            "businessOrg": {
                **application_org(row, "BUSINESS_ORG"),
                "superDepartment": row.get("SUPER_DEPARTMENT"),
                "department": row.get("DEPARTMENT"),
                "busOrgLgNm": row.get("BUS_ORG_LG_NM"),
            },
            "bu": {
                **application_org(row, "BU"),
                "buSuperDepartment": row.get("BU_SUPER_DEPARTMENT"),
                "buDepartment": row.get("BU_DEPARTMENT"),
            },
        },
        "owners": owners,
    }


def _peers(connection, month: str, row: dict) -> dict:
    level1 = row.get("SUPER_DIVISION") or ""
    lifecycle = row.get("LIFECYCLE_PHASE") or ""
    counts = repository.peers(connection, month, level1, lifecycle)
    return {
        "definitionId": "PD-17",
        "applications": counts["applications"],
        "nonCompliantApplications": counts["nonCompliantApplications"],
        "nonCompliantShare": share(counts["nonCompliantApplications"], counts["applications"]),
        "basis": {"l1": level1, "lifecycle": lifecycle},
    }


def _previous_observed(rows: list[dict], month: str):
    earlier = [row for row in rows if row["MONTH_END"] < month]
    if not earlier:
        return None
    return earlier[-1]


def _changes(previous: dict, current: dict, month: str) -> list[dict]:
    found = []
    for field, column in _FIELDS:
        old = _text(previous.get(column))
        new = _text(current.get(column))
        if old != new:
            found.append({"field": field, "from": old, "to": new, "month": month})
    return found


def _text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _person(row: dict, first: str, last: str) -> str:
    return f"{row.get(first) or ''} {row.get(last) or ''}".strip()
