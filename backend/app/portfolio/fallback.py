"""Packaged extracts for the six dashboard responses. Numbers come only from the export files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.common.v2_envelope import DATASET_VERSION
from app.portfolio import definitions
from app.portfolio.coerce import as_bool, as_date, as_int, as_timestamp
from app.portfolio.definitions import POPULATION_NOTE
from app.portfolio.month import prior_in_index
from app.portfolio.scope import Scope
from app.portfolio.support import count_value, org_ref, paginate, share_value, sort_by

_FILES = {
    "overview": "overview.json",
    "trends": "monthly_trends.json",
    "testing": "testing.json",
    "risk": "risk_distribution.json",
    "org": "org_contribution.json",
    "applications": "application_register.json",
}

_PACKAGED = {
    "code": "PACKAGED_DATA",
    "message": "Showing the packaged extract because Snowflake did not answer. Figures are limited to the exported month and the default filters.",
}


def roots() -> list[Path]:
    here = Path(__file__).resolve()
    app_dir = here.parents[1]
    repo = here.parents[3]
    return [
        app_dir / "fallback_assets" / "v2",
        repo / "snowflake" / "mock_data_setup" / "export",
    ]


def available() -> bool:
    return _load("overview") is not None and _load("trends") is not None


def latest_month() -> str | None:
    rows = _load("trends") or []
    months = [as_date(row.get("REPORTING_MONTHEND_DATE")) for row in rows]
    months = [month for month in months if month]
    if not months:
        return None
    return max(months)


def dataset_meta() -> dict:
    overview = (_load("overview") or [{}])[0]
    trends = _load("trends") or []
    version = overview.get("DATASET_VERSION") or DATASET_VERSION
    row_count = sum(int(row.get("METRIC_ROWS") or 0) for row in trends)
    return {"version": version, "rowCount": row_count, "promotedAt": None}


def eligible(scope: Scope | None, month: str | None, *, ignore_month: bool = False) -> bool:
    if not available():
        return False
    if scope is not None and not scope.unfiltered():
        return False
    latest = latest_month()
    if ignore_month:
        return True
    if month and month != latest:
        return False
    if scope is not None and scope.month and scope.month != latest:
        return False
    return True


def status_data() -> dict:
    overview = (_load("overview") or [{}])[0]
    trends = _sorted(_load("trends") or [])
    latest = trends[-1]["REPORTING_MONTHEND_DATE"] if trends else None
    meta = dataset_meta()
    return {
        "latestMonth": latest,
        "months": len(trends),
        "dataset": {
            "version": overview.get("DATASET_VERSION") or meta["version"],
            "rowCount": meta["rowCount"],
            "promotedAt": None,
        },
        "source": "packaged",
        "definitionsVersion": definitions.DEFINITIONS_VERSION,
        "agents": {"analysis": "unavailable", "data": "unavailable"},
    }


def overview_data() -> dict:
    row = (_load("overview") or [{}])[0]
    trends = {item["REPORTING_MONTHEND_DATE"]: item for item in _sorted(_load("trends") or [])}
    testing = {item["REPORTING_MONTHEND_DATE"]: item for item in _sorted(_load("testing") or [])}
    month = row.get("REPORTING_MONTHEND_DATE")
    prior_month = prior_in_index(month, list(trends)) if month else None
    prior = trends.get(prior_month) if prior_month else None
    prior_test = testing.get(prior_month) if prior_month else None
    apps = int(row.get("APPLICATIONS_REPORTING") or 0)
    nc = int(row.get("NON_COMPLIANT_APPLICATIONS") or 0)
    prior_apps = int(prior["APPLICATIONS_REPORTING"]) if prior else None
    prior_nc = int(prior["NON_COMPLIANT_APPLICATIONS"]) if prior else None
    return {
        "month": month,
        "previousMonth": prior_month,
        "applicationsReporting": count_value(apps, prior_apps),
        "nonCompliant": {
            "applications": count_value(nc, prior_nc),
            "share": share_value(nc, apps, prior_nc, prior_apps),
        },
        "testing": {
            "withoutCompletedTest": count_value(
                row.get("APPLICATIONS_WITHOUT_COMPLETED_TEST"),
                None if prior_test is None else prior_test.get("APPLICATIONS_WITHOUT_COMPLETED_TEST"),
            ),
            "withFailedTest": count_value(
                row.get("APPLICATIONS_WITH_FAILED_TEST"),
                None if prior_test is None else prior_test.get("APPLICATIONS_WITH_FAILED_TEST"),
            ),
        },
        "openFindings": count_value(row.get("OPEN_FINDINGS"), None if prior is None else prior.get("OPEN_FINDINGS")),
        "metricRows": count_value(row.get("METRIC_ROWS"), None if prior is None else prior.get("METRIC_ROWS")),
        "movement": {
            "newlyNonCompliant": int(row.get("NEWLY_NON_COMPLIANT") or 0),
            "resolved": int(row.get("RESOLVED") or 0),
            "persistentNonCompliant": int(row.get("PERSISTENT_NON_COMPLIANT") or 0),
            "noPriorMonth": int(row.get("NO_PRIOR_MONTH") or 0),
            "notNonCompliantBothMonths": int(row.get("NOT_NON_COMPLIANT_BOTH_MONTHS") or 0),
        },
        "freshness": {
            "datasetVersion": row.get("DATASET_VERSION") or DATASET_VERSION,
            "snapshotGeneratedAt": as_timestamp(row.get("SNAPSHOT_GENERATED_AT")),
            "sourceRowCount": int(row.get("SOURCE_ROW_COUNT") or 0),
        },
    }


def trends_data(month_from: str | None, month_to: str | None) -> dict:
    testing = {item["REPORTING_MONTHEND_DATE"]: item for item in _load("testing") or []}
    points = []
    rows = _sorted(_load("trends") or [])
    first = rows[0]["REPORTING_MONTHEND_DATE"] if rows else None
    for row in rows:
        month = row["REPORTING_MONTHEND_DATE"]
        if month_from and month < month_from:
            continue
        if month_to and month > month_to:
            continue
        test = testing.get(month) or {}
        apps = int(row.get("APPLICATIONS_REPORTING") or 0)
        nc = int(row.get("NON_COMPLIANT_APPLICATIONS") or 0)
        first_month = month == first
        points.append(
            {
                "month": month,
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": definitions.share(nc, apps),
                "withoutCompletedTest": int(test.get("APPLICATIONS_WITHOUT_COMPLETED_TEST") or 0),
                "withFailedTest": int(test.get("APPLICATIONS_WITH_FAILED_TEST") or 0),
                "newlyNonCompliant": None if first_month else int(row.get("NEWLY_NON_COMPLIANT") or 0),
                "resolved": None if first_month else int(row.get("RESOLVED") or 0),
                "persistentNonCompliant": None if first_month else int(row.get("PERSISTENT_NON_COMPLIANT") or 0),
                "metricRows": int(row.get("METRIC_ROWS") or 0),
                "openFindings": int(row.get("OPEN_FINDINGS") or 0),
            }
        )
    return {"points": points, "note": dict(POPULATION_NOTE)}


def testing_data(series: bool) -> dict:
    rows = _sorted(_load("testing") or [])
    latest = rows[-1] if rows else {}
    data = {
        "month": latest.get("REPORTING_MONTHEND_DATE"),
        "byTestStatus": None,
        "completedTestResults": None,
        "applications": {
            "withoutCompletedTest": int(latest.get("APPLICATIONS_WITHOUT_COMPLETED_TEST") or 0),
            "withFailedTest": int(latest.get("APPLICATIONS_WITH_FAILED_TEST") or 0),
            "reporting": int(latest.get("APPLICATIONS_REPORTING") or 0),
        },
    }
    if series:
        data["series"] = [
            {
                "month": row["REPORTING_MONTHEND_DATE"],
                "applicationsReporting": int(row.get("APPLICATIONS_REPORTING") or 0),
                "withoutCompletedTest": int(row.get("APPLICATIONS_WITHOUT_COMPLETED_TEST") or 0),
                "withFailedTest": int(row.get("APPLICATIONS_WITH_FAILED_TEST") or 0),
            }
            for row in rows
        ]
    return data


def risk_data() -> dict:
    rows = list(_load("risk") or [])
    total = sum(int(row.get("APPLICATIONS_REPORTING") or 0) for row in rows)
    items = []
    for row in sorted(rows, key=lambda item: str(item.get("RISK_CODE") or "")):
        apps = int(row.get("APPLICATIONS_REPORTING") or 0)
        nc = int(row.get("NON_COMPLIANT_APPLICATIONS") or 0)
        key = str(row.get("RISK_CODE") or "")
        items.append(
            {
                "key": key,
                "label": key,
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": definitions.share(nc, apps),
                "share": definitions.share(apps, total),
            }
        )
    month = latest_month()
    return {
        "month": month,
        "dimension": "risk",
        "items": items,
        "definitionIds": ["PD-08", "PD-11"],
    }


def org_data(level: int, parent: str | None, sort_field: str, direction: str, page: int, page_size: int) -> dict:
    rows = [row for row in (_load("org") or []) if row.get("HIERARCHY_NAME") == "BUSINESS_ORG"]
    buckets: dict[tuple, dict] = {}
    for row in rows:
        level1 = row.get("LEVEL_1")
        level2 = row.get("LEVEL_2")
        if level == 2 and parent and level1 != parent:
            continue
        bucket_id = (level1,) if level == 1 else (level1, level2)
        bucket = buckets.setdefault(
            bucket_id,
            {
                "key": level1 if level == 1 else level2,
                "label": level1 if level == 1 else level2,
                "org": org_ref("BUSINESS_ORG", level1, None if level == 1 else level2),
                "applicationsReporting": 0,
                "nonCompliantApplications": 0,
                "openFindings": 0,
                "findingsSeen": False,
            },
        )
        bucket["applicationsReporting"] += int(row.get("APPLICATIONS_REPORTING") or 0)
        bucket["nonCompliantApplications"] += int(row.get("NON_COMPLIANT_APPLICATIONS") or 0)
        if row.get("OPEN_FINDINGS") is not None:
            bucket["openFindings"] += int(row["OPEN_FINDINGS"])
            bucket["findingsSeen"] = True
    items = []
    for bucket in buckets.values():
        apps = bucket["applicationsReporting"]
        nc = bucket["nonCompliantApplications"]
        items.append(
            {
                "key": bucket["key"],
                "label": bucket["label"],
                "org": bucket["org"],
                "applicationsReporting": apps,
                "nonCompliantApplications": nc,
                "nonCompliantShare": definitions.share(nc, apps),
                "contributionShare": None,
                "newlyNonCompliant": None,
                "resolved": None,
                "withoutCompletedTest": None,
                "withFailedTest": None,
                "openFindings": bucket["openFindings"] if bucket["findingsSeen"] else None,
            }
        )
    total_apps = sum(item["applicationsReporting"] for item in items)
    total_nc = sum(item["nonCompliantApplications"] for item in items)
    for item in items:
        item["contributionShare"] = definitions.share(item["nonCompliantApplications"], total_nc)
    items = _sort_org(items, sort_field, direction)
    page_items, page_block = paginate(items, page, page_size)
    return {
        "month": latest_month(),
        "orgTree": "BUSINESS_ORG",
        "level": level,
        "parent": parent,
        "totals": {"applicationsReporting": total_apps, "nonCompliantApplications": total_nc},
        "items": page_items,
        "page": page_block,
    }


def applications_data(attention: str | None, q: str | None, sort_field: str, direction: str, page: int, page_size: int) -> dict:
    items = [_application(row) for row in (_load("applications") or [])]
    if attention:
        items = [item for item in items if _attention(item, attention)]
    if q:
        needle = q.upper()
        items = [
            item
            for item in items
            if item["eonId"].upper().startswith(needle) or needle in item["applicationName"].upper()
        ]
    items = _sort_apps(items, sort_field, direction)
    matching = len(items)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["org"]["level1"]] = counts.get(item["org"]["level1"], 0) + 1
    top = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    page_items, page_block = paginate(items, page, page_size)
    return {
        "month": latest_month(),
        "items": page_items,
        "summary": {"matching": matching, "byOrgLevel1": [{"key": key, "count": count} for key, count in top]},
        "page": page_block,
    }


def warnings(*extra: dict) -> list[dict]:
    return [_PACKAGED, *extra]


def partial_warning(message: str) -> dict:
    return {"code": "PACKAGED_DATA", "message": message}


def _application(row: dict) -> dict:
    return {
        "eonId": row.get("EON_ID"),
        "applicationName": row.get("APPLICATION_NAME"),
        "org": org_ref("BUSINESS_ORG", row.get("SUPER_DIVISION"), None),
        "legalEntityCode": None,
        "tier": int(row.get("APPLICATION_TIER") or 0),
        "risk": row.get("ASSET_RISK_RATING_2"),
        "lifecycle": row.get("LIFECYCLE_PHASE"),
        "isNonCompliant": as_bool(row.get("IS_NON_COMPLIANT_APP")),
        "hasNoCompletedTest": as_bool(row.get("HAS_NO_COMPLETED_TEST")),
        "hasFailedTest": as_bool(row.get("HAS_FAILED_TEST")),
        "movement": row.get("MOVEMENT_STATUS"),
        "metricsReported": None,
        "metricRows": int(row.get("METRIC_ROWS") or 0),
        "nonCompliantRows": None,
        "openFindings": as_int(row.get("OPEN_FINDINGS")),
        "nonCompliantSince": None,
    }


def _attention(item: dict, attention: str) -> bool:
    return {
        "nonCompliant": item["isNonCompliant"],
        "noCompletedTest": item["hasNoCompletedTest"],
        "failedTest": item["hasFailedTest"],
        "newlyNonCompliant": item["movement"] == "NEWLY_NON_COMPLIANT",
        "resolved": item["movement"] == "RESOLVED",
        "persistentNonCompliant": item["movement"] == "PERSISTENT_NON_COMPLIANT",
    }[attention]


def _sort_org(items: list, field: str, direction: str) -> list:
    getters = {
        "nonCompliant": lambda item: item["nonCompliantApplications"],
        "share": lambda item: item["nonCompliantShare"],
        "reporting": lambda item: item["applicationsReporting"],
        "openFindings": lambda item: item["openFindings"],
        "name": lambda item: item["label"] or "",
    }
    return sort_by(items, getters[field], direction == "desc", lambda item: item["label"] or "")


def _sort_apps(items: list, field: str, direction: str) -> list:
    getters = {
        "name": lambda item: item["applicationName"] or "",
        "openFindings": lambda item: item["openFindings"],
        "metricRows": lambda item: item["metricRows"],
        "org": lambda item: item["org"]["level1"] or "",
    }
    return sort_by(items, getters[field], direction == "desc", lambda item: item["eonId"] or "")


def _sorted(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: row.get("REPORTING_MONTHEND_DATE") or "")


@lru_cache(maxsize=16)
def _load(kind: str):
    name = _FILES[kind]
    for root in roots():
        path = root / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None
