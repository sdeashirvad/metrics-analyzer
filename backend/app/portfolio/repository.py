"""Portfolio SQL. The only module that queries Snowflake for V2 portfolio reads.

User values are bound parameters. Column names, sort expressions and dimensions
come from the allow-lists in this file.
"""

from __future__ import annotations

import logging

from app.db.connection import fetch_all, fetch_one
from app.portfolio.coerce import as_date, as_int, as_number, as_timestamp
from app.portfolio.definitions import classify_denominator
from app.portfolio.objects import APPLICATION_COMPLIANCE, APPLICATION_MONTH, SNAPSHOT
from app.portfolio.scope import Scope

logger = logging.getLogger(__name__)

ORG_COLUMNS = {
    "BUSINESS_ORG": ("SUPER_DIVISION", "DIVISION"),
    "BU": ("BU_SUPER_DIVISION", "BU_DIVISION"),
}

DISTRIBUTION_COLUMNS = {
    "risk": "ASSET_RISK_RATING_2",
    "tier": "APPLICATION_TIER",
    "lifecycle": "LIFECYCLE_PHASE",
    "rto": "APPLICATION_RTO",
    "legalEntity": "LEGAL_ENTITY_CODE",
}

BREAKDOWN_COLUMNS = {
    "legalEntity": ("LEGAL_ENTITY_CODE", "LEGAL_ENTITY_NAME"),
    "tier": ("APPLICATION_TIER", "APPLICATION_TIER"),
    "risk": ("ASSET_RISK_RATING_2", "ASSET_RISK_RATING_2"),
    "lifecycle": ("LIFECYCLE_PHASE", "LIFECYCLE_PHASE"),
    "complianceReason": ("COMPLIANCE_REASON", "COMPLIANCE_REASON"),
    "testStatus": ("TEST_STATUS", "TEST_STATUS"),
}

ATTENTION_SQL = {
    "nonCompliant": "a.IS_NON_COMPLIANT_APP = 1",
    "noCompletedTest": "a.HAS_NO_COMPLETED_TEST = 1",
    "failedTest": "a.HAS_FAILED_TEST = 1",
    "newlyNonCompliant": "a.MOVEMENT_STATUS = 'NEWLY_NON_COMPLIANT'",
    "resolved": "a.MOVEMENT_STATUS = 'RESOLVED'",
    "persistentNonCompliant": "a.MOVEMENT_STATUS = 'PERSISTENT_NON_COMPLIANT'",
}

_DATE_COLUMNS = {
    "MONTH_END",
    "REPORTING_MONTHEND_DATE",
    "FIRST_MONTH",
    "LAST_MONTH",
    "SINCE",
    "NON_COMPLIANT_SINCE",
}
_TS_COLUMNS = {"PROMOTED_AT", "SNAPSHOT_GENERATED_AT"}


def latest_reporting_month(connection) -> str | None:
    row = _one(
        connection,
        f"SELECT MAX(REPORTING_MONTHEND_DATE) AS MONTH_END FROM {APPLICATION_MONTH}",
    )
    if not row:
        return None
    return as_date(row.get("MONTH_END"))


def probe(connection) -> dict:
    row = _one(
        connection,
        f"SELECT COUNT(*) AS ROW_COUNT, MAX(PROMOTED_AT) AS PROMOTED_AT FROM {APPLICATION_COMPLIANCE}",
    ) or {}
    months = _all(
        connection,
        f"""
        SELECT REPORTING_MONTHEND_DATE AS MONTH_END
        FROM {APPLICATION_MONTH}
        GROUP BY 1
        ORDER BY 1
        """,
    )
    values = [item["MONTH_END"] for item in months if item.get("MONTH_END")]
    from app.common.v2_envelope import DATASET_VERSION

    return {
        "version": DATASET_VERSION,
        "rowCount": int(row.get("ROW_COUNT") or 0),
        "promotedAt": row.get("PROMOTED_AT"),
        "latestMonth": values[-1] if values else None,
        "months": values,
    }


def catalog(connection, latest_month: str) -> dict:
    months = _all(
        connection,
        f"""
        SELECT REPORTING_MONTHEND_DATE AS MONTH_END,
               COUNT(*) AS APPLICATIONS_REPORTING,
               COALESCE(SUM(METRIC_ROWS), 0) AS METRIC_ROWS
        FROM {APPLICATION_MONTH}
        GROUP BY 1
        ORDER BY 1
        """,
    )
    business_l1 = _level1(connection, "SUPER_DIVISION", latest_month)
    bu_l1 = _level1(connection, "BU_SUPER_DIVISION", latest_month)
    business_l2 = _level2(connection, "SUPER_DIVISION", "DIVISION")
    bu_l2 = _level2(connection, "BU_SUPER_DIVISION", "BU_DIVISION")
    attributes = _all(
        connection,
        f"""
        SELECT LEGAL_ENTITY_CODE,
               ANY_VALUE(LEGAL_ENTITY_NAME) AS LEGAL_ENTITY_NAME,
               APPLICATION_TIER,
               ASSET_RISK_RATING_2,
               LIFECYCLE_PHASE,
               IS_MERGERS_ACQUISITIONS_ASSET
        FROM {APPLICATION_MONTH}
        GROUP BY LEGAL_ENTITY_CODE, APPLICATION_TIER, ASSET_RISK_RATING_2,
                 LIFECYCLE_PHASE, IS_MERGERS_ACQUISITIONS_ASSET
        """,
    )
    vocab_rows = _all(
        connection,
        f"""
        SELECT COMPLIANCE_STATUS, TEST_STATUS, TEST_RESULT, COMPLIANCE_REASON
        FROM {APPLICATION_COMPLIANCE}
        GROUP BY 1, 2, 3, 4
        """,
    )
    movement = _all(
        connection,
        f"SELECT MOVEMENT_STATUS FROM {APPLICATION_MONTH} GROUP BY 1",
    )
    metrics = _all(
        connection,
        f"""
        SELECT METRIC_ID,
               COUNT(*) AS "ROWS",
               MIN(REPORTING_MONTHEND_DATE) AS FIRST_MONTH,
               MAX(REPORTING_MONTHEND_DATE) AS LAST_MONTH,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending') AS PENDING_ROWS,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending' AND IS_DENOMINATOR = 1) AS PENDING_IN
        FROM {APPLICATION_COMPLIANCE}
        GROUP BY METRIC_ID
        ORDER BY METRIC_ID
        """,
    )
    legal = {}
    tiers = set()
    risks = set()
    lifecycles = set()
    for row in attributes:
        if row.get("LEGAL_ENTITY_CODE"):
            legal[row["LEGAL_ENTITY_CODE"]] = row.get("LEGAL_ENTITY_NAME") or row["LEGAL_ENTITY_CODE"]
        if row.get("APPLICATION_TIER") is not None:
            tiers.add(int(row["APPLICATION_TIER"]))
        if row.get("ASSET_RISK_RATING_2"):
            risks.add(row["ASSET_RISK_RATING_2"])
        if row.get("LIFECYCLE_PHASE"):
            lifecycles.add(row["LIFECYCLE_PHASE"])
    compliance, test_status, test_result, reasons = set(), set(), set(), set()
    for row in vocab_rows:
        if row.get("COMPLIANCE_STATUS"):
            compliance.add(row["COMPLIANCE_STATUS"])
        if row.get("TEST_STATUS"):
            test_status.add(row["TEST_STATUS"])
        if row.get("TEST_RESULT"):
            test_result.add(row["TEST_RESULT"])
        if row.get("COMPLIANCE_REASON"):
            reasons.add(row["COMPLIANCE_REASON"])
    metric_map = {}
    for row in metrics:
        metric_map[row["METRIC_ID"]] = {
            "metricId": row["METRIC_ID"],
            "rows": int(row["ROWS"] or 0),
            "firstMonth": row["FIRST_MONTH"],
            "lastMonth": row["LAST_MONTH"],
            "denominatorScope": classify_denominator(row.get("PENDING_ROWS") or 0, row.get("PENDING_IN") or 0),
        }
    return {
        "months": [
            {
                "month": row["MONTH_END"],
                "applicationsReporting": int(row["APPLICATIONS_REPORTING"] or 0),
                "metricRows": int(row["METRIC_ROWS"] or 0),
            }
            for row in months
        ],
        "trees": {
            "BUSINESS_ORG": {"level1": [row["VALUE"] for row in business_l1], "level2": [row["VALUE"] for row in business_l2], "level1Rows": business_l1, "level2Rows": business_l2},
            "BU": {"level1": [row["VALUE"] for row in bu_l1], "level2": [row["VALUE"] for row in bu_l2], "level1Rows": bu_l1, "level2Rows": bu_l2},
        },
        "legal": [{"code": code, "name": legal[code]} for code in sorted(legal)],
        "legalEntities": sorted(legal),
        "tiers": sorted(tiers),
        "risks": sorted(risks),
        "lifecycles": sorted(lifecycles),
        "complianceStatus": sorted(compliance),
        "testStatus": sorted(test_status),
        "testResult": sorted(test_result),
        "complianceReason": sorted(reasons),
        "movement": sorted(row["MOVEMENT_STATUS"] for row in movement if row.get("MOVEMENT_STATUS")),
        "metrics": metric_map,
    }


def app_month_totals(connection, scope: Scope, months: list[str] | None) -> list[dict]:
    params: dict = {}
    month_sql = "1=1"
    if months:
        month_sql = _in_sql("REPORTING_MONTHEND_DATE", months, params, "tot_month")
    where = scope_sql(scope, params, skip_levels=False)
    return _all(
        connection,
        f"""
        SELECT REPORTING_MONTHEND_DATE AS MONTH_END,
               COUNT(*) AS APPLICATIONS_REPORTING,
               COALESCE(SUM(IS_NON_COMPLIANT_APP), 0) AS NON_COMPLIANT,
               COALESCE(SUM(HAS_NO_COMPLETED_TEST), 0) AS NO_TEST,
               COALESCE(SUM(HAS_FAILED_TEST), 0) AS FAILED,
               SUM(OPEN_FINDINGS) AS OPEN_FINDINGS,
               COALESCE(SUM(METRIC_ROWS), 0) AS METRIC_ROWS,
               COUNT_IF(MOVEMENT_STATUS = 'NEWLY_NON_COMPLIANT') AS NEWLY,
               COUNT_IF(MOVEMENT_STATUS = 'RESOLVED') AS RESOLVED,
               COUNT_IF(MOVEMENT_STATUS = 'PERSISTENT_NON_COMPLIANT') AS PERSISTENT,
               COUNT_IF(MOVEMENT_STATUS = 'NO_PRIOR_MONTH') AS NO_PRIOR,
               COUNT_IF(MOVEMENT_STATUS = 'NOT_NON_COMPLIANT_BOTH_MONTHS') AS NOT_BOTH
        FROM {APPLICATION_MONTH}
        WHERE {month_sql} AND {where}
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )


def metric_status_counts(connection, scope: Scope, month: str) -> list[dict]:
    params: dict = {}
    where = scope_sql(scope, params, month=month)
    return _all(
        connection,
        f"""
        SELECT COMPLIANCE_STATUS AS STATUS, COUNT(*) AS "ROWS"
        FROM {APPLICATION_COMPLIANCE}
        WHERE {where}
        GROUP BY 1
        """,
        params,
    )


def top_reasons(connection, scope: Scope, month: str) -> list[dict]:
    params: dict = {}
    where = scope_sql(scope, params, month=month)
    return _all(
        connection,
        f"""
        SELECT COMPLIANCE_REASON AS REASON,
               COUNT(*) AS "ROWS",
               COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant') AS NON_COMPLIANT_ROWS
        FROM {APPLICATION_COMPLIANCE}
        WHERE {where}
        GROUP BY 1
        ORDER BY "ROWS" DESC, REASON ASC
        LIMIT 8
        """,
        params,
    )


def status_precedence(connection, scope: Scope, month: str) -> list[dict]:
    params: dict = {}
    where = scope_sql(scope, params, month=month)
    return _all(
        connection,
        f"""
        SELECT STATUS, COUNT(*) AS APPLICATIONS
        FROM (
            SELECT EON_ID,
                   CASE
                       WHEN COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant') > 0 THEN 'NON_COMPLIANT'
                       WHEN COUNT_IF(COMPLIANCE_STATUS = 'Pending') > 0 THEN 'PENDING'
                       WHEN COUNT_IF(COMPLIANCE_STATUS = 'Compliant') > 0 THEN 'COMPLIANT'
                       ELSE 'NOT_APPLICABLE'
                   END AS STATUS
            FROM {APPLICATION_COMPLIANCE}
            WHERE {where}
            GROUP BY EON_ID
        )
        GROUP BY STATUS
        """,
        params,
    )


def test_distribution(connection, scope: Scope, month: str) -> tuple[list[dict], dict]:
    params: dict = {}
    where = scope_sql(scope, params, month=month)
    by_status = _all(
        connection,
        f"""
        SELECT TEST_STATUS, COUNT(*) AS "ROWS", COUNT(DISTINCT EON_ID) AS APPS
        FROM {APPLICATION_COMPLIANCE}
        WHERE {where}
        GROUP BY 1
        """,
        params,
    )
    params2: dict = {}
    where2 = scope_sql(scope, params2, month=month)
    results = _one(
        connection,
        f"""
        SELECT COUNT_IF(TEST_STATUS = 'Test_Complete' AND TEST_RESULT = 'Pass') AS PASS,
               COUNT_IF(TEST_STATUS = 'Test_Complete' AND TEST_RESULT = 'Fail') AS FAIL,
               COUNT_IF(TEST_STATUS = 'Test_Complete' AND TEST_RESULT IS NULL) AS NOT_RECORDED
        FROM {APPLICATION_COMPLIANCE}
        WHERE {where2}
        """,
        params2,
    ) or {}
    return by_status, results


def attribute_distribution(connection, scope: Scope, month: str, dimension: str) -> list[dict]:
    column = DISTRIBUTION_COLUMNS[dimension]
    params: dict = {}
    where = scope_sql(scope, params, month=month)
    label = "ANY_VALUE(LEGAL_ENTITY_NAME)" if dimension == "legalEntity" else column
    return _all(
        connection,
        f"""
        SELECT {column} AS ITEM_KEY,
               {label} AS ITEM_LABEL,
               COUNT(*) AS APPLICATIONS_REPORTING,
               COALESCE(SUM(IS_NON_COMPLIANT_APP), 0) AS NON_COMPLIANT
        FROM {APPLICATION_MONTH}
        WHERE {where}
        GROUP BY {column}
        ORDER BY {column}
        """,
        params,
    )


def org_groups(connection, scope: Scope, month: str, level: int, parent: str | None) -> list[dict]:
    level1, level2 = ORG_COLUMNS[scope.org_tree]
    params: dict = {}
    where = scope_sql(scope, params, month=month, skip_levels=True)
    if level == 1:
        group = level1
        extra = ""
        select_l2 = "CAST(NULL AS VARCHAR)"
    else:
        group = f"{level1}, {level2}"
        select_l2 = level2
        extra = ""
        if parent:
            params["parent"] = parent
            extra = f" AND {level1} = %(parent)s"
    return _all(
        connection,
        f"""
        SELECT {level1} AS LEVEL1,
               {select_l2} AS LEVEL2,
               COUNT(*) AS APPLICATIONS_REPORTING,
               COALESCE(SUM(IS_NON_COMPLIANT_APP), 0) AS NON_COMPLIANT,
               COUNT_IF(MOVEMENT_STATUS = 'NEWLY_NON_COMPLIANT') AS NEWLY,
               COUNT_IF(MOVEMENT_STATUS = 'RESOLVED') AS RESOLVED,
               COALESCE(SUM(HAS_NO_COMPLETED_TEST), 0) AS NO_TEST,
               COALESCE(SUM(HAS_FAILED_TEST), 0) AS FAILED,
               SUM(OPEN_FINDINGS) AS OPEN_FINDINGS
        FROM {APPLICATION_MONTH}
        WHERE {where}{extra}
        GROUP BY {group}
        """,
        params,
    )


def coverage(connection, month: str) -> dict:
    totals = _one(
        connection,
        f"""
        SELECT COUNT(DISTINCT EON_ID) AS APPS,
               COUNT(DISTINCT METRIC_ID) AS METRICS,
               COUNT(*) AS "ROWS",
               MIN(REPORTING_MONTHEND_DATE) AS FIRST_MONTH,
               MAX(REPORTING_MONTHEND_DATE) AS LAST_MONTH,
               COUNT(DISTINCT REPORTING_MONTHEND_DATE) AS MONTHS
        FROM {APPLICATION_COMPLIANCE}
        """,
    ) or {}
    app_months = _one(connection, f"SELECT COUNT(*) AS N FROM {APPLICATION_MONTH}") or {}
    reporting = _one(
        connection,
        f"SELECT COUNT(*) AS N FROM {APPLICATION_MONTH} WHERE REPORTING_MONTHEND_DATE = %(month)s",
        {"month": month},
    ) or {}
    spans = _one(
        connection,
        f"""
        SELECT COUNT_IF(MONTHS_SEEN = %(month_count)s) AS ALL_MONTHS,
               COUNT_IF(MONTHS_SEEN = 1) AS ONE_MONTH
        FROM (
            SELECT EON_ID, COUNT(DISTINCT REPORTING_MONTHEND_DATE) AS MONTHS_SEEN
            FROM {APPLICATION_COMPLIANCE}
            GROUP BY EON_ID
        )
        """,
        {"month_count": int(totals.get("MONTHS") or 0)},
    ) or {}
    return {
        "applicationsInDataset": int(totals.get("APPS") or 0),
        "metricsInDataset": int(totals.get("METRICS") or 0),
        "metricRowsInDataset": int(totals.get("ROWS") or 0),
        "applicationMonthsInDataset": int(app_months.get("N") or 0),
        "applicationsReporting": int(reporting.get("N") or 0),
        "observedInAllMonths": int(spans.get("ALL_MONTHS") or 0),
        "observedInOneMonthOnly": int(spans.get("ONE_MONTH") or 0),
        "first": totals.get("FIRST_MONTH"),
        "last": totals.get("LAST_MONTH"),
        "monthCount": int(totals.get("MONTHS") or 0),
    }


def application_rows(connection, scope: Scope, month: str, attention: str | None, q: str | None, metric_id: str | None) -> list[dict]:
    params = {"month": month}
    where = scope_sql(scope, params, prefix="a", month=month)
    extra = []
    if attention:
        extra.append(ATTENTION_SQL[attention])
    if q:
        params["q"] = q
        extra.append(
            "(STARTSWITH(UPPER(a.EON_ID), UPPER(%(q)s)) OR CONTAINS(UPPER(a.APPLICATION_NAME), UPPER(%(q)s)))"
        )
    if metric_id:
        params["metric_id"] = metric_id
        extra.append(
            f"""a.EON_ID IN (
                SELECT EON_ID FROM {APPLICATION_COMPLIANCE}
                WHERE METRIC_ID = %(metric_id)s AND REPORTING_MONTHEND_DATE = %(month)s
            )"""
        )
    extra_sql = (" AND " + " AND ".join(extra)) if extra else ""
    return _all(
        connection,
        f"""
        WITH nc AS (
            SELECT EON_ID,
                   REPORTING_MONTHEND_DATE,
                   DATEDIFF('month', TO_DATE('2000-01-01'), REPORTING_MONTHEND_DATE)
                       - ROW_NUMBER() OVER (PARTITION BY EON_ID ORDER BY REPORTING_MONTHEND_DATE) AS ISLAND
            FROM {APPLICATION_MONTH}
            WHERE IS_NON_COMPLIANT_APP = 1
        ),
        starts AS (
            SELECT EON_ID, ISLAND, MIN(REPORTING_MONTHEND_DATE) AS SINCE
            FROM nc
            GROUP BY EON_ID, ISLAND
        ),
        current_since AS (
            SELECT n.EON_ID, s.SINCE
            FROM nc n
            JOIN starts s ON s.EON_ID = n.EON_ID AND s.ISLAND = n.ISLAND
            WHERE n.REPORTING_MONTHEND_DATE = %(month)s
        ),
        first_month AS (
            SELECT MIN(REPORTING_MONTHEND_DATE) AS FIRST_MONTH FROM {APPLICATION_MONTH}
        )
        SELECT a.EON_ID, a.APPLICATION_NAME, a.SUPER_DIVISION, a.DIVISION,
               a.BU_SUPER_DIVISION, a.BU_DIVISION, a.LEGAL_ENTITY_CODE, a.APPLICATION_TIER,
               a.ASSET_RISK_RATING_2, a.LIFECYCLE_PHASE, a.IS_NON_COMPLIANT_APP,
               a.HAS_NO_COMPLETED_TEST, a.HAS_FAILED_TEST, a.MOVEMENT_STATUS,
               a.METRICS_REPORTED, a.METRIC_ROWS, a.NON_COMPLIANT_ROWS, a.OPEN_FINDINGS,
               CASE
                   WHEN a.IS_NON_COMPLIANT_APP <> 1 THEN NULL
                   WHEN current_since.SINCE IS NULL THEN NULL
                   WHEN current_since.SINCE = first_month.FIRST_MONTH THEN NULL
                   ELSE current_since.SINCE
               END AS NON_COMPLIANT_SINCE
        FROM {APPLICATION_MONTH} a
        LEFT JOIN current_since ON current_since.EON_ID = a.EON_ID
        CROSS JOIN first_month
        WHERE {where}{extra_sql}
        """,
        params,
    )


def metric_month_aggregates(connection, scope: Scope, metric_id: str | None = None) -> list[dict]:
    params: dict = {}
    where = scope_sql(scope, params)
    metric_sql = ""
    if metric_id:
        params["metric_id"] = metric_id
        metric_sql = " AND METRIC_ID = %(metric_id)s"
    return _all(
        connection,
        f"""
        SELECT METRIC_ID,
               REPORTING_MONTHEND_DATE AS MONTH_END,
               COUNT(*) AS APPLICATIONS,
               COALESCE(SUM(IS_NUMERATOR), 0) AS NUMERATOR,
               COALESCE(SUM(IS_DENOMINATOR), 0) AS DENOMINATOR,
               COUNT_IF(COMPLIANCE_STATUS = 'Compliant') AS COMPLIANT,
               COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant') AS NON_COMPLIANT,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending') AS PENDING,
               COUNT_IF(COMPLIANCE_STATUS = 'Not_Applicable') AS NOT_APPLICABLE,
               COUNT_IF(TEST_STATUS = 'Test_Complete') AS TEST_COMPLETE,
               COUNT_IF(TEST_STATUS = 'Test_Pending') AS TEST_PENDING,
               COUNT_IF(TEST_STATUS = 'No_Test') AS TEST_NONE,
               COUNT_IF(TEST_STATUS = 'Exempt') AS TEST_EXEMPT,
               COUNT_IF(TEST_RESULT = 'Pass') AS RESULT_PASS,
               COUNT_IF(TEST_RESULT = 'Fail') AS RESULT_FAIL,
               COUNT_IF(TEST_RESULT IS NULL) AS RESULT_MISSING,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending' AND IS_DENOMINATOR = 0) AS PENDING_EXCLUDED,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending' AND IS_DENOMINATOR = 1) AS PENDING_INCLUDED
        FROM {APPLICATION_COMPLIANCE}
        WHERE {where}{metric_sql}
        GROUP BY METRIC_ID, REPORTING_MONTHEND_DATE
        """,
        params,
    )


def metric_movements(connection, scope: Scope, month: str, prior: str | None, metric_id: str | None = None) -> list[dict]:
    if prior is None:
        return []
    params = {"prior": prior}
    where = scope_sql(scope, params, prefix="cur", month=month)
    metric_sql = ""
    if metric_id:
        params["metric_id"] = metric_id
        metric_sql = " AND cur.METRIC_ID = %(metric_id)s"
    return _all(
        connection,
        f"""
        SELECT cur.METRIC_ID,
               CASE
                   WHEN pri.EON_ID IS NULL THEN 'NO_PRIOR_MONTH'
                   WHEN cur.COMPLIANCE_STATUS = 'Non_Compliant' AND pri.COMPLIANCE_STATUS = 'Non_Compliant' THEN 'PERSISTENT_NON_COMPLIANT'
                   WHEN cur.COMPLIANCE_STATUS = 'Non_Compliant' THEN 'NEWLY_NON_COMPLIANT'
                   WHEN pri.COMPLIANCE_STATUS = 'Non_Compliant' THEN 'RESOLVED'
                   ELSE 'OTHER'
               END AS MOVEMENT,
               COUNT(*) AS N
        FROM {APPLICATION_COMPLIANCE} cur
        LEFT JOIN {APPLICATION_COMPLIANCE} pri
          ON pri.METRIC_ID = cur.METRIC_ID
         AND pri.EON_ID = cur.EON_ID
         AND pri.REPORTING_MONTHEND_DATE = %(prior)s
        WHERE {where}{metric_sql}
        GROUP BY 1, 2
        """,
        params,
    )


def metric_exists(connection, metric_id: str) -> bool:
    row = _one(
        connection,
        f"SELECT 1 AS FOUND FROM {APPLICATION_COMPLIANCE} WHERE METRIC_ID = %(metric_id)s LIMIT 1",
        {"metric_id": metric_id},
    )
    return bool(row)


def denominator_for(connection, metric_id: str) -> str:
    row = _one(
        connection,
        f"""
        SELECT COUNT_IF(COMPLIANCE_STATUS = 'Pending') AS PENDING_ROWS,
               COUNT_IF(COMPLIANCE_STATUS = 'Pending' AND IS_DENOMINATOR = 1) AS PENDING_IN
        FROM {APPLICATION_COMPLIANCE}
        WHERE METRIC_ID = %(metric_id)s
        """,
        {"metric_id": metric_id},
    ) or {}
    return classify_denominator(row.get("PENDING_ROWS") or 0, row.get("PENDING_IN") or 0)


def metric_eon_rows(connection, scope: Scope, metric_id: str) -> list[dict]:
    params = {"metric_id": metric_id}
    where = scope_sql(scope, params)
    return _all(
        connection,
        f"""
        SELECT REPORTING_MONTHEND_DATE AS MONTH_END,
               EON_ID,
               IS_NUMERATOR,
               IS_DENOMINATOR,
               COMPLIANCE_STATUS
        FROM {APPLICATION_COMPLIANCE}
        WHERE METRIC_ID = %(metric_id)s AND {where}
        """,
        params,
    )


def metric_breakdown(connection, scope: Scope, metric_id: str, months: list[str], dimension: str, level: int, parent: str | None) -> list[dict]:
    params = {"metric_id": metric_id}
    where = scope_sql(scope, params, skip_levels=dimension == "org")
    month_sql = _in_sql("REPORTING_MONTHEND_DATE", months, params, "bd_month")
    if dimension == "org":
        level1, level2 = ORG_COLUMNS[scope.org_tree]
        if level == 1:
            key_sql, label_sql, group = level1, level1, level1
            parent_sql = ""
        else:
            key_sql, label_sql = level2, level2
            group = f"{level1}, {level2}"
            parent_sql = ""
            if parent:
                params["parent"] = parent
                parent_sql = f" AND {level1} = %(parent)s"
        return _all(
            connection,
            f"""
            SELECT REPORTING_MONTHEND_DATE AS MONTH_END,
                   {key_sql} AS ITEM_KEY,
                   {label_sql} AS ITEM_LABEL,
                   COUNT(*) AS APPLICATIONS,
                   COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant') AS NON_COMPLIANT,
                   COALESCE(SUM(IS_NUMERATOR), 0) AS NUMERATOR,
                   COALESCE(SUM(IS_DENOMINATOR), 0) AS DENOMINATOR
            FROM {APPLICATION_COMPLIANCE}
            WHERE METRIC_ID = %(metric_id)s AND {month_sql} AND {where}{parent_sql}
            GROUP BY REPORTING_MONTHEND_DATE, {group}
            """,
            params,
        )
    key_col, label_col = BREAKDOWN_COLUMNS[dimension]
    return _all(
        connection,
        f"""
        SELECT REPORTING_MONTHEND_DATE AS MONTH_END,
               {key_col} AS ITEM_KEY,
               ANY_VALUE({label_col}) AS ITEM_LABEL,
               COUNT(*) AS APPLICATIONS,
               COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant') AS NON_COMPLIANT,
               COALESCE(SUM(IS_NUMERATOR), 0) AS NUMERATOR,
               COALESCE(SUM(IS_DENOMINATOR), 0) AS DENOMINATOR
        FROM {APPLICATION_COMPLIANCE}
        WHERE METRIC_ID = %(metric_id)s AND {month_sql} AND {where}
        GROUP BY REPORTING_MONTHEND_DATE, {key_col}
        """,
        params,
    )


def metric_application_rows(connection, scope: Scope, metric_id: str, month: str, prior: str | None) -> list[dict]:
    params = {"metric_id": metric_id, "prior": prior}
    where = scope_sql(scope, params, prefix="ac", month=month)
    return _all(
        connection,
        f"""
        SELECT ac.EON_ID, ac.APPLICATION_NAME, ac.SUPER_DIVISION, ac.DIVISION,
               ac.BU_SUPER_DIVISION, ac.BU_DIVISION, ac.LEGAL_ENTITY_CODE,
               ac.COMPLIANCE_STATUS, ac.COMPLIANCE_REASON, ac.TEST_STATUS, ac.TEST_RESULT,
               ac.IS_NUMERATOR, ac.IS_DENOMINATOR, ac.RFB, am.OPEN_FINDINGS,
               pri.COMPLIANCE_STATUS AS PRIOR_STATUS
        FROM {APPLICATION_COMPLIANCE} ac
        LEFT JOIN {APPLICATION_MONTH} am
          ON am.EON_ID = ac.EON_ID AND am.REPORTING_MONTHEND_DATE = ac.REPORTING_MONTHEND_DATE
        LEFT JOIN {APPLICATION_COMPLIANCE} pri
          ON pri.EON_ID = ac.EON_ID
         AND pri.METRIC_ID = ac.METRIC_ID
         AND pri.REPORTING_MONTHEND_DATE = %(prior)s
        WHERE ac.METRIC_ID = %(metric_id)s AND {where}
        """,
        params,
    )


def application_months(connection, eon_id: str) -> list[dict]:
    return _all(
        connection,
        f"""
        SELECT EON_ID, APPLICATION_NAME, REPORTING_MONTHEND_DATE AS MONTH_END,
               APPLICATION_TIER, ASSET_RISK_RATING_2, LIFECYCLE_PHASE, APPLICATION_RTO,
               LEGAL_ENTITY_CODE, LEGAL_ENTITY_NAME, IS_MERGERS_ACQUISITIONS_ASSET,
               SUPER_DIVISION, DIVISION, SUPER_DEPARTMENT, DEPARTMENT, BUS_ORG_LG_NM,
               BU_SUPER_DIVISION, BU_DIVISION, BU_SUPER_DEPARTMENT, BU_DEPARTMENT,
               PRIMARY_BUS_FIRST_NAME, PRIMARY_BUS_LAST_NAME,
               PRIMARY_IT_FIRST_NAME, PRIMARY_IT_LAST_NAME,
               IS_NON_COMPLIANT_APP, HAS_NO_COMPLETED_TEST, HAS_FAILED_TEST, MOVEMENT_STATUS,
               METRICS_REPORTED, METRIC_ROWS, NON_COMPLIANT_ROWS, OPEN_FINDINGS
        FROM {APPLICATION_MONTH}
        WHERE EON_ID = %(eon_id)s
        ORDER BY REPORTING_MONTHEND_DATE
        """,
        {"eon_id": eon_id},
    )


def application_metric_rows(connection, eon_id: str) -> list[dict]:
    return _all(
        connection,
        f"""
        SELECT METRIC_ID, REPORTING_MONTHEND_DATE AS MONTH_END, COMPLIANCE_STATUS, COMPLIANCE_REASON,
               TEST_STATUS, TEST_RESULT, IS_NUMERATOR, IS_DENOMINATOR, RFB
        FROM {APPLICATION_COMPLIANCE}
        WHERE EON_ID = %(eon_id)s
        ORDER BY METRIC_ID, REPORTING_MONTHEND_DATE
        """,
        {"eon_id": eon_id},
    )


def peers(connection, month: str, level1: str, lifecycle: str) -> dict:
    row = _one(
        connection,
        f"""
        SELECT COUNT(*) AS APPLICATIONS,
               COALESCE(SUM(IS_NON_COMPLIANT_APP), 0) AS NON_COMPLIANT
        FROM {APPLICATION_MONTH}
        WHERE REPORTING_MONTHEND_DATE = %(month)s
          AND SUPER_DIVISION = %(level1)s
          AND LIFECYCLE_PHASE = %(lifecycle)s
        """,
        {"month": month, "level1": level1, "lifecycle": lifecycle},
    ) or {}
    return {
        "applications": int(row.get("APPLICATIONS") or 0),
        "nonCompliantApplications": int(row.get("NON_COMPLIANT") or 0),
    }


def snapshot(connection, month: str) -> dict | None:
    from app.common.v2_envelope import DATASET_VERSION

    try:
        row = _one(
            connection,
            f"""
            SELECT DATASET_VERSION, SNAPSHOT_GENERATED_AT, SOURCE_ROW_COUNT
            FROM {SNAPSHOT}
            WHERE REPORTING_MONTHEND_DATE = %(month)s
              AND DATASET_VERSION = %(version)s
            ORDER BY SNAPSHOT_GENERATED_AT DESC
            LIMIT 1
            """,
            {"month": month, "version": DATASET_VERSION},
        )
    except Exception as exc:
        logger.info("snapshot unread error=%s", type(exc).__name__)
        return None
    if not row:
        return None
    return {
        "version": row.get("DATASET_VERSION") or DATASET_VERSION,
        "generatedAt": row.get("SNAPSHOT_GENERATED_AT"),
        "sourceRowCount": as_int(row.get("SOURCE_ROW_COUNT")),
    }


def scope_sql(scope: Scope, params: dict, *, prefix: str = "", month: str | None = None, skip_levels: bool = False) -> str:
    column = f"{prefix}." if prefix else ""
    clauses = []
    if month:
        key = _unique(params, "month")
        params[key] = month
        clauses.append(f"{column}REPORTING_MONTHEND_DATE = %({key})s")
    if not skip_levels:
        level1, level2 = ORG_COLUMNS[scope.org_tree]
        _add_in(clauses, params, f"{column}{level1}", scope.l1, "l1")
        _add_in(clauses, params, f"{column}{level2}", scope.l2, "l2")
    _add_in(clauses, params, f"{column}LEGAL_ENTITY_CODE", scope.legal_entity, "le")
    _add_in(clauses, params, f"{column}APPLICATION_TIER", scope.tier, "tier")
    _add_in(clauses, params, f"{column}ASSET_RISK_RATING_2", scope.risk, "risk")
    _add_in(clauses, params, f"{column}LIFECYCLE_PHASE", scope.lifecycle, "life")
    if scope.ma:
        key = _unique(params, "ma")
        params[key] = scope.ma
        clauses.append(f"{column}IS_MERGERS_ACQUISITIONS_ASSET = %({key})s")
    if not clauses:
        return "1=1"
    return " AND ".join(clauses)


def _level1(connection, column: str, month: str) -> list[dict]:
    if column not in {"SUPER_DIVISION", "BU_SUPER_DIVISION"}:
        raise KeyError(column)
    return _all(
        connection,
        f"""
        SELECT {column} AS VALUE, COUNT(*) AS APPLICATIONS
        FROM {APPLICATION_MONTH}
        WHERE REPORTING_MONTHEND_DATE = %(month)s
        GROUP BY 1
        ORDER BY 1
        """,
        {"month": month},
    )


def _level2(connection, parent: str, child: str) -> list[dict]:
    if (parent, child) not in {("SUPER_DIVISION", "DIVISION"), ("BU_SUPER_DIVISION", "BU_DIVISION")}:
        raise KeyError((parent, child))
    return _all(
        connection,
        f"""
        SELECT {child} AS VALUE, {parent} AS PARENT
        FROM {APPLICATION_MONTH}
        GROUP BY 1, 2
        ORDER BY 2, 1
        """,
    )


def _add_in(clauses: list[str], params: dict, column: str, values, name: str) -> None:
    if not values:
        return
    clauses.append(_in_sql(column, list(values), params, name))


def _in_sql(column: str, values: list, params: dict, name: str) -> str:
    keys = []
    for value in values:
        key = _unique(params, name)
        params[key] = value
        keys.append(f"%({key})s")
    return f"{column} IN ({', '.join(keys)})"


def _unique(params: dict, name: str) -> str:
    key = name
    index = 0
    while key in params:
        index += 1
        key = f"{name}_{index}"
    return key


def _all(connection, sql: str, params: dict | None = None) -> list[dict]:
    return [_record(row) for row in fetch_all(connection, sql, params or {})]


def _one(connection, sql: str, params: dict | None = None) -> dict | None:
    row = fetch_one(connection, sql, params or {})
    if row is None:
        return None
    return _record(row)


def _record(row: dict) -> dict:
    item = {}
    for key, value in row.items():
        name = str(key).upper()
        if name in _DATE_COLUMNS:
            item[name] = as_date(value)
        elif name in _TS_COLUMNS:
            item[name] = as_timestamp(value)
        else:
            item[name] = as_number(value)
    return item
