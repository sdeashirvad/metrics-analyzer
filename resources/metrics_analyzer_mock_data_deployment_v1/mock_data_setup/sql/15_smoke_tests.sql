-- =====================================================================================
-- 15_smoke_tests.sql
-- Read-only. Runs the semantic view with SEMANTIC_VIEW() and compares with values computed from the delivered CSV.
-- Each test states the expected result. Any mismatch: STOP and capture the test number and the actual output.
-- Status: UNEXECUTED. Run as the setup role first, then repeat tests 15.1-15.3 as METRICS_ANALYZER_DEMO_VIEWER.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 15.1 Application counts, latest month.
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.reporting_month_end
  METRICS app_month.applications_reporting, app_month.non_compliant_applications, app_month.applications_without_completed_test
) WHERE reporting_month_end = '2026-10-31';
-- Expected: 2026-10-31 | 923 | 300 | 293

-- 15.2 Movement (provisional definition), latest month.
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.reporting_month_end
  METRICS app_month.newly_non_compliant_applications, app_month.resolved_applications
) WHERE reporting_month_end = '2026-10-31';
-- Expected: 2026-10-31 | 132 | 117

-- 15.3 Open findings, ONE month only.
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.reporting_month_end
  METRICS app_month.open_findings
) WHERE reporting_month_end = '2026-10-31';
-- Expected: 2026-10-31 | 1870

-- 15.4 Observation-level metrics joined through the relationship (rows, tests, provisional rate), latest month.
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.reporting_month_end
  METRICS obs.observation_rows, obs.failed_test_rows, obs.passed_test_rows, obs.numerator_total, obs.denominator_total, obs.provisional_compliance_rate
) WHERE reporting_month_end = '2026-10-31';
-- Expected: 2026-10-31 | rows 1096 | failed 273 | passed 459 | numerator 463 | denominator 873 | rate 0.5304 (PROVISIONAL)

-- 15.5 Application metric split by an application dimension (golden question G03).
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.super_division, app_month.reporting_month_end
  METRICS app_month.non_compliant_applications, app_month.applications_reporting
) WHERE reporting_month_end = '2026-10-31'
ORDER BY non_compliant_applications DESC, super_division LIMIT 6;
-- Expected: (Super_Division_04, 65, 194, 0.335) ; (Super_Division_02, 50, 137, 0.365) ; (Super_Division_05, 48, 144, 0.333) ; (Super_Division_06, 37, 128, 0.289) ; (Super_Division_08, 36, 111, 0.324) ; (Super_Division_03, 33, 105, 0.314)

-- 15.6 Row metric split by an observation dimension (golden question G08).
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS obs.compliance_status, app_month.reporting_month_end
  METRICS obs.observation_rows
) WHERE reporting_month_end = '2026-10-31'
ORDER BY observation_rows DESC;
-- Expected: (Compliant, 463) ; (Non_Compliant, 324) ; (Pending, 183) ; (Not_Applicable, 126)

-- 15.7 Trend (golden question G06).
SELECT * FROM SEMANTIC_VIEW(
  METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  DIMENSIONS app_month.reporting_month_end
  METRICS app_month.non_compliant_applications, app_month.applications_reporting
) ORDER BY reporting_month_end;
-- Expected 12 rows: (2025-11-30, 197, 596) ; (2025-12-31, 206, 652) ; (2026-01-31, 234, 708) ; (2026-02-28, 247, 745) ; (2026-03-31, 264, 780) ; (2026-04-30, 272, 814) ; (2026-05-31, 290, 842) ; (2026-06-30, 282, 903) ; (2026-07-31, 294, 922) ; (2026-08-31, 312, 962) ; (2026-09-30, 278, 937) ; (2026-10-31, 300, 923)

-- 15.8 Self-check: semantic view versus the base objects, latest month. status must be PASS in every row.
WITH sv AS (
  SELECT * FROM SEMANTIC_VIEW(
    METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
    DIMENSIONS app_month.reporting_month_end
    METRICS app_month.non_compliant_applications, obs.observation_rows, obs.failed_test_rows
  ) WHERE reporting_month_end = '2026-10-31'
), base AS (
  SELECT (SELECT SUM(IS_NON_COMPLIANT_APP) FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31') AS nc_apps,
         (SELECT COUNT(*) FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31') AS obs_rows,
         (SELECT COUNT_IF(TEST_STATUS='Test_Complete' AND TEST_RESULT='Fail') FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31') AS failed
)
SELECT 'non_compliant_applications' AS test, sv.non_compliant_applications AS semantic_view, base.nc_apps AS base_sql,
       IFF(sv.non_compliant_applications = base.nc_apps, 'PASS', 'FAIL') AS status FROM sv, base
UNION ALL SELECT 'observation_rows', sv.observation_rows, base.obs_rows, IFF(sv.observation_rows = base.obs_rows, 'PASS', 'FAIL') FROM sv, base
UNION ALL SELECT 'failed_test_rows', sv.failed_test_rows, base.failed, IFF(sv.failed_test_rows = base.failed, 'PASS', 'FAIL') FROM sv, base;

-- 15.9 Agent test (manual, in Snowsight): AI & ML > Agents > AGENT_APPLICATION_COMPLIANCE_V1 > Playground.
--      Ask each question in agent/golden_questions.md and compare. Expected behaviours are listed there.
--      Mandatory behavioural checks: (a) "What is the compliance rate?" is answered as PROVISIONAL with numerator and denominator;
--      (b) "Which applications are most critical?" is NOT answered by ranking tier/risk codes (it asks or offers a defined alternative);
--      (c) "How many applications are non-compliant?" with no month uses 2026-10-31 and says so.
