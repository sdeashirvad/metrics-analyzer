"""Write local JSON extracts from MOCK_DATA. Uses backend settings. Prints no credentials."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

BACKEND = Path(r"C:\Users\aashirvad\Documents\ControlLens\metrics-analyzer\backend")
sys.path.insert(0, str(BACKEND))

from app.config import load_settings  # noqa: E402
import snowflake.connector  # noqa: E402

OUT = Path(__file__).resolve().parent


def encode(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def rows(cur):
    names = [c[0] for c in cur.description]
    return [{name: encode(value) for name, value in zip(names, row)} for row in cur.fetchall()]


def main():
    settings = load_settings()
    connection = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse="COMPUTE_WH",
        database="METRICS_ANALYZER",
        schema="MOCK_DATA",
        role="ACCOUNTADMIN",
        login_timeout=60,
    )
    queries = {
        "overview.json": """
            SELECT * FROM APP_PORTFOLIO_MONTHLY_SNAPSHOT
            WHERE DATASET_VERSION = 'v1-seed20261103' AND REPORTING_MONTHEND_DATE = '2026-10-31'
        """,
        "monthly_trends.json": """
            SELECT REPORTING_MONTHEND_DATE, APPLICATIONS_REPORTING, NON_COMPLIANT_APPLICATIONS,
                   NEWLY_NON_COMPLIANT, RESOLVED, PERSISTENT_NON_COMPLIANT, METRIC_ROWS, OPEN_FINDINGS
            FROM APP_PORTFOLIO_MONTHLY_SNAPSHOT
            WHERE DATASET_VERSION = 'v1-seed20261103'
            ORDER BY REPORTING_MONTHEND_DATE
        """,
        "testing.json": """
            SELECT REPORTING_MONTHEND_DATE, APPLICATIONS_REPORTING,
                   APPLICATIONS_WITHOUT_COMPLETED_TEST, APPLICATIONS_WITH_FAILED_TEST
            FROM APP_PORTFOLIO_MONTHLY_SNAPSHOT
            WHERE DATASET_VERSION = 'v1-seed20261103'
            ORDER BY REPORTING_MONTHEND_DATE
        """,
        "risk_distribution.json": """
            SELECT ASSET_RISK_RATING_2 AS RISK_CODE, COUNT(*) AS APPLICATIONS_REPORTING,
                   SUM(IS_NON_COMPLIANT_APP) AS NON_COMPLIANT_APPLICATIONS
            FROM V_APPLICATION_MONTH_STATUS
            WHERE REPORTING_MONTHEND_DATE = '2026-10-31'
            GROUP BY ASSET_RISK_RATING_2
            ORDER BY ASSET_RISK_RATING_2
        """,
        "org_contribution.json": """
            SELECT HIERARCHY_NAME, LEVEL_1, LEVEL_2, APPLICATIONS_REPORTING,
                   NON_COMPLIANT_APPLICATIONS, OPEN_FINDINGS
            FROM V_ORGANIZATION_MONTHLY_SUMMARY
            WHERE REPORTING_MONTHEND_DATE = '2026-10-31'
            ORDER BY HIERARCHY_NAME, NON_COMPLIANT_APPLICATIONS DESC, LEVEL_1, LEVEL_2
        """,
        "application_register.json": """
            SELECT EON_ID, APPLICATION_NAME, APPLICATION_TIER, SUPER_DIVISION, BU_SUPER_DIVISION,
                   LIFECYCLE_PHASE, ASSET_RISK_RATING_2, IS_NON_COMPLIANT_APP, HAS_NO_COMPLETED_TEST,
                   HAS_FAILED_TEST, MOVEMENT_STATUS, METRIC_ROWS, OPEN_FINDINGS
            FROM V_APPLICATION_MONTH_STATUS
            WHERE REPORTING_MONTHEND_DATE = '2026-10-31'
            ORDER BY EON_ID
        """,
        "application_metric_rows.json": """
            SELECT EON_ID, METRIC_ID, METRIC_DATE, COMPLIANCE_STATUS, COMPLIANCE_REASON,
                   TEST_STATUS, TEST_RESULT, IS_NUMERATOR, IS_DENOMINATOR, RFB, TOTAL_RFB
            FROM APPLICATION_COMPLIANCE
            WHERE REPORTING_MONTHEND_DATE = '2026-10-31'
              AND EON_ID = (
                  SELECT EON_ID FROM V_APPLICATION_MONTH_STATUS
                  WHERE REPORTING_MONTHEND_DATE = '2026-10-31' AND IS_NON_COMPLIANT_APP = 1
                  ORDER BY EON_ID LIMIT 1
              )
            ORDER BY METRIC_ID
        """,
    }
    try:
        cursor = connection.cursor()
        for name, sql in queries.items():
            cursor.execute(sql)
            payload = rows(cursor)
            (OUT / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(name, len(payload))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
