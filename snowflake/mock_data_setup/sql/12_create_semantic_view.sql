-- =====================================================================================
-- 12_create_semantic_view.sql
-- Native Snowflake semantic view for Cortex Analyst: METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
-- Two logical tables, one validated relationship:
--   app_month = V_APPLICATION_MONTH_STATUS (application x month; unique by construction: GROUP BY EON_ID, month)
--   obs       = APPLICATION_COMPLIANCE     (application x metric x month rows)
--   obs (EON_ID, REPORTING_MONTHEND_DATE) REFERENCES app_month   -> every obs row has exactly one app_month row.
-- Clause order follows the CREATE SEMANTIC VIEW reference: TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS,
-- COMMENT, AI_SQL_GENERATION, AI_QUESTION_CATEGORIZATION. Status: UNEXECUTED (syntax checked against the docs only).
-- IF NOT EXISTS: re-running does not overwrite. To upgrade, create ..._V2 (see SEMANTIC_MODEL.md).
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = 'ACCOUNTADMIN';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = 'COMPUTE_WH';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

CREATE SEMANTIC VIEW IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1
  TABLES (
    app_month AS METRICS_ANALYZER.MOCK_DATA.V_APPLICATION_MONTH_STATUS
      PRIMARY KEY (EON_ID, REPORTING_MONTHEND_DATE)
      WITH SYNONYMS = ('application', 'application month', 'app', 'EON')
      COMMENT = 'One row per application (EON_ID) per reporting month. Holds application attributes (organisation, owner, tier, risk codes, legal entity) as of that month and application-level compliance flags. Count applications from here.',
    obs AS METRICS_ANALYZER.MOCK_DATA.APPLICATION_COMPLIANCE
      WITH SYNONYMS = ('observation', 'metric row', 'test record')
      COMMENT = 'One row per application per metric per month-end (EON_ID x METRIC_ID x METRIC_DATE). Holds the test status, test result, compliance status and reason. A row is NOT an application: one application can have several rows in a month.'
  )
  RELATIONSHIPS (
    obs_to_app_month AS obs (EON_ID, REPORTING_MONTHEND_DATE) REFERENCES app_month (EON_ID, REPORTING_MONTHEND_DATE)
  )
  FACTS (
    obs.numerator_flag    AS IS_NUMERATOR   COMMENT = 'PROVISIONAL. 1 if the row counts toward a compliance-rate numerator. Meaning depends on the metric definition, which the client has not supplied.',
    obs.denominator_flag  AS IS_DENOMINATOR COMMENT = 'PROVISIONAL. 1 if the row counts toward a compliance-rate denominator. Meaning depends on the metric definition, which the client has not supplied.',
    obs.row_findings      AS RFB            COMMENT = 'PROVISIONAL. Row-level count of findings/remediation items (RFB). Blank for about 1% of rows. Exact business meaning not supplied.',
    obs.system_rtc_flag   AS SYSTEM_RTC     COMMENT = 'PROVISIONAL. 0/1 flag. Meaning not supplied by the client; do not interpret beyond the raw flag.'
  )
  DIMENSIONS (
    -- ---- time ----
    app_month.reporting_month_end AS REPORTING_MONTHEND_DATE WITH SYNONYMS = ('reporting month', 'month', 'month end', 'period', 'reporting period', 'metric date') COMMENT = 'Month-end reporting date (2025-11-30 to 2026-10-31). Equals METRIC_DATE on every row. Always filter or group by this when comparing periods.',
    app_month.reporting_month AS REPORTING_MONTH WITH SYNONYMS = ('month number') COMMENT = 'Calendar month number 1-12 derived from the reporting date. Not unique across years: use reporting_month_end for periods.',
    app_month.reporting_year  AS REPORTING_YEAR  WITH SYNONYMS = ('year') COMMENT = 'Four-digit year of the reporting date.',
    -- ---- application identity ----
    app_month.eon_id              AS EON_ID           WITH SYNONYMS = ('EON ID', 'application id', 'application key', 'entity id') COMMENT = 'Synthetic application key. Primary entity key.',
    app_month.application_name    AS APPLICATION_NAME WITH SYNONYMS = ('app name', 'application') COMMENT = 'Synthetic application name, one-to-one with EON_ID.',
    app_month.grn                 AS GRN              WITH SYNONYMS = ('global resource name') COMMENT = 'Synthetic globally formatted resource name, stable per EON_ID.',
    app_month.lifecycle_phase     AS LIFECYCLE_PHASE  WITH SYNONYMS = ('lifecycle', 'phase', 'application stage') COMMENT = 'Lifecycle stage: Planning, Development, Implementation, Production, Retirement.',
    app_month.is_ma_asset         AS IS_MERGERS_ACQUISITIONS_ASSET WITH SYNONYMS = ('M&A asset', 'merger acquisition asset', 'acquired application') COMMENT = 'Y if the application is associated with a (fictional) acquired entity, else N.',
    app_month.acquired_entity     AS ACQUIRED_ENTITY  WITH SYNONYMS = ('acquisition', 'acquired company') COMMENT = 'Fictional acquired-entity label, or NON_ACQUIRED_ENTITY.',
    -- ---- criticality and recovery attributes (NO severity direction is defined for any of these codes) ----
    app_month.application_tier    AS APPLICATION_TIER WITH SYNONYMS = ('tier', 'criticality tier') COMMENT = 'Tier 1-4. The sources do not say whether a low or high number is more critical. Never rank by it.',
    app_month.application_rto     AS APPLICATION_RTO  WITH SYNONYMS = ('RTO', 'recovery time objective') COMMENT = 'Recovery-time-objective band: RTO_0_1H, RTO_1_4H, RTO_4_12H, RTO_12_24H, RTO_24_72H, RTO_GT_72H.',
    app_month.rto_change_date     AS RTO_CHANGE_DATE  WITH SYNONYMS = ('RTO change') COMMENT = 'Date the RTO was last changed on or before the reporting date. Blank if never changed.',
    app_month.asset_risk_rating   AS ASSET_RISK_RATING_2 WITH SYNONYMS = ('risk code', 'risk rating', 'P code', 'asset risk rating') COMMENT = 'Risk code P1-P4. The sources do not define which end is most critical. Do not assume P1 is highest risk.',
    app_month.arr_availability    AS ARR_AVAILABILITY    WITH SYNONYMS = ('availability rating') COMMENT = 'Availability component A1-A4. No severity direction defined.',
    app_month.arr_confidentiality AS ARR_CONFIDENTIALITY WITH SYNONYMS = ('confidentiality rating') COMMENT = 'Confidentiality component C1-C4. No severity direction defined.',
    app_month.arr_integrity       AS ARR_INTEGRITY       WITH SYNONYMS = ('integrity rating') COMMENT = 'Integrity component I1-I4. No severity direction defined.',
    app_month.has_critical_kbs    AS HAS_CTIRICAL_KBS    WITH SYNONYMS = ('critical KBS', 'critical knowledge base', 'HAS_CRITICAL_KBS', 'CTIRICAL') COMMENT = 'Y/N critical knowledge-base / business-service designation. Source column spelling is HAS_CTIRICAL_KBS (kept as supplied).',
    app_month.kbs_flag            AS KBS_FLAG_FLAG       WITH SYNONYMS = ('KBS flag') COMMENT = 'Y/N secondary KBS flag; equals has_critical_kbs in this dataset.',
    -- ---- organisation hierarchy 2 (business organisation) ----
    app_month.super_division      AS SUPER_DIVISION      WITH SYNONYMS = ('business organisation top level', 'org super division') COMMENT = 'ORGANISATION HIERARCHY 2, level 1 (top). Parent of division. Default hierarchy when the user says "division", "department" or "organisation" without saying BU.',
    app_month.division            AS DIVISION            WITH SYNONYMS = ('org division') COMMENT = 'ORGANISATION HIERARCHY 2, level 2. Child of super_division.',
    app_month.super_department    AS SUPER_DEPARTMENT    WITH SYNONYMS = ('org super department') COMMENT = 'ORGANISATION HIERARCHY 2, level 3. Child of division. Always populated.',
    app_month.department          AS DEPARTMENT          WITH SYNONYMS = ('org department') COMMENT = 'ORGANISATION HIERARCHY 2, level 4. NULL for the 11% of application-months classified at super-department level (org_group_type = SUPER_DEPARTMENT). Group at super_department when mixing.',
    app_month.org_group_type      AS ORG_GROUP_TYPE      WITH SYNONYMS = ('org level', 'organisation level') COMMENT = 'DEPARTMENT or SUPER_DEPARTMENT: the level at which the record is classified. Controls whether department is populated.',
    app_month.business_org_name   AS BUS_ORG_LG_NM       WITH SYNONYMS = ('business org', 'business organisation name') COMMENT = 'Business organisation label that follows the lowest populated level of hierarchy 2.',
    -- ---- organisation hierarchy 1 (business unit, BU) ----
    app_month.bu_super_division   AS BU_SUPER_DIVISION   WITH SYNONYMS = ('BU super division', 'business unit top level') COMMENT = 'BUSINESS UNIT HIERARCHY 1, level 1 (top). Use ONLY when the user says BU or business unit.',
    app_month.bu_division         AS BU_DIVISION         WITH SYNONYMS = ('BU division') COMMENT = 'BUSINESS UNIT HIERARCHY 1, level 2.',
    app_month.bu_super_department AS BU_SUPER_DEPARTMENT WITH SYNONYMS = ('BU super department') COMMENT = 'BUSINESS UNIT HIERARCHY 1, level 3.',
    app_month.bu_department       AS BU_DEPARTMENT       WITH SYNONYMS = ('BU department') COMMENT = 'BUSINESS UNIT HIERARCHY 1, level 4. NULL when org_group_type = SUPER_DEPARTMENT.',
    -- ---- cost centre, legal entity, bank groupings ----
    app_month.cost_center_code    AS COST_CENTER_CODE    WITH SYNONYMS = ('cost centre code', 'CC') COMMENT = 'Synthetic cost-centre code, one-to-one with cost_center_name.',
    app_month.cost_center_name    AS COST_CENTER_NAME    WITH SYNONYMS = ('cost centre', 'cost center') COMMENT = 'Synthetic cost-centre name.',
    app_month.legal_entity_code   AS LEGAL_ENTITY_CODE   WITH SYNONYMS = ('LE code', 'entity code') COMMENT = 'Synthetic legal-entity code, one-to-one with legal_entity_name.',
    app_month.legal_entity_name   AS LEGAL_ENTITY_NAME   WITH SYNONYMS = ('legal entity', 'LE', 'entity') COMMENT = 'Fictional legal-entity name (40 values).',
    app_month.is_bank_a           AS IS_USBANKS          WITH SYNONYMS = ('BANK_A', 'US banks flag', 'bank group A', 'IS_USBANKS') COMMENT = 'Y/N: the legal entity belongs to generic bank grouping BANK_A (source column IS_USBANKS). Attribute of the legal entity.',
    app_month.is_bank_b           AS IS_MSBNA            WITH SYNONYMS = ('BANK_B', 'bank group B', 'IS_MSBNA') COMMENT = 'Y/N: the legal entity belongs to generic bank grouping BANK_B (source column IS_MSBNA).',
    app_month.is_bank_c           AS IS_MSPBNA           WITH SYNONYMS = ('BANK_C', 'bank group C', 'IS_MSPBNA') COMMENT = 'Y/N: the legal entity belongs to generic bank grouping BANK_C (source column IS_MSPBNA).',
    app_month.bank_groupings      AS USBANKS_LE_LIST     WITH SYNONYMS = ('bank group list', 'USBANKS_LE_LIST') COMMENT = 'Pipe-delimited list of the BANK_A/BANK_B/BANK_C groupings the legal entity belongs to. NULL if none.',
    -- ---- location ----
    app_month.building_name       AS BUILDING_NAME       WITH SYNONYMS = ('application building') COMMENT = 'Primary building of the application.',
    app_month.event_location      AS EVENT_LOCATION      WITH SYNONYMS = ('location', 'site') COMMENT = 'Location of the application building (determined by building_name).',
    app_month.employee_building   AS EMPLOYEE_BUILDING_NAME WITH SYNONYMS = ('owner building') COMMENT = 'Building of the business owner.',
    app_month.employee_country    AS EMPLOYEE_COUNTRY_NAME  WITH SYNONYMS = ('country', 'owner country') COMMENT = 'Country (neutral label) of the business owner building.',
    -- ---- owners (fictional people) ----
    app_month.business_owner      AS TRIM(PRIMARY_BUS_FIRST_NAME || ' ' || PRIMARY_BUS_LAST_NAME) WITH SYNONYMS = ('business owner', 'primary business owner', 'owner') COMMENT = 'Fictional primary business owner (first + last name).',
    app_month.it_owner            AS TRIM(PRIMARY_IT_FIRST_NAME || ' ' || PRIMARY_IT_LAST_NAME)   WITH SYNONYMS = ('IT owner', 'technology owner', 'primary IT owner') COMMENT = 'Fictional primary technology owner (first + last name).',
    -- ---- application-month status (provisional movement) ----
    app_month.movement_status     AS MOVEMENT_STATUS     WITH SYNONYMS = ('movement', 'deterioration', 'change in compliance') COMMENT = 'PROVISIONAL. Compares the application with the immediately preceding calendar month: NEWLY_NON_COMPLIANT, RESOLVED, PERSISTENT_NON_COMPLIANT, NOT_NON_COMPLIANT_BOTH_MONTHS, or NO_PRIOR_MONTH (not reported the month before).',
    app_month.is_non_compliant_app AS IS_NON_COMPLIANT_APP COMMENT = '1 if the application has at least one Non_Compliant metric row in the month, else 0.',
    -- ---- observation attributes ----
    obs.metric_id                 AS METRIC_ID           WITH SYNONYMS = ('metric', 'control', 'metric code') COMMENT = 'Metric identifier (24 values). Repeats across applications and months; not a row key. No metric names or families are supplied.',
    obs.metric_date_type          AS METRIC_DATE_TYPE    COMMENT = 'Reporting-date convention; always Monthend.',
    obs.test_status               AS TEST_STATUS         WITH SYNONYMS = ('testing status', 'test state') COMMENT = 'Test_Complete, Test_Pending, No_Test or Exempt.',
    obs.test_result               AS TEST_RESULT         WITH SYNONYMS = ('test outcome', 'pass or fail') COMMENT = 'Pass or Fail. NULL unless the test is complete (63 completed tests also have no result).',
    obs.compliance_status         AS COMPLIANCE_STATUS   WITH SYNONYMS = ('compliance', 'status', 'compliant', 'non compliant') COMMENT = 'Compliant, Non_Compliant, Pending or Not_Applicable.',
    obs.compliance_reason         AS COMPLIANCE_REASON   WITH SYNONYMS = ('reason', 'driver', 'why non compliant') COMMENT = 'Reason supporting the compliance status (18 values, e.g. Requirements_Met, Test_Failed, Remediation_Overdue).',
    obs.exemption_level_1         AS EXEMPTION_LEVEL_1   WITH SYNONYMS = ('exemption') COMMENT = 'Exemption classification, mostly populated when the test status is Exempt.'
  )
  METRICS (
    -- ---- application-level (count applications here; each application counted once) ----
    app_month.applications_reporting AS COUNT(DISTINCT app_month.EON_ID)
      WITH SYNONYMS = ('number of applications', 'application count', 'apps reporting', 'distinct applications')
      COMMENT = 'Distinct applications with at least one metric row in the selected period. Counts each application once.',
    app_month.non_compliant_applications AS COUNT(DISTINCT IFF(app_month.IS_NON_COMPLIANT_APP = 1, app_month.EON_ID, NULL))
      WITH SYNONYMS = ('non compliant apps', 'applications not compliant', 'non-compliant exposure')
      COMMENT = 'Distinct applications with at least one Non_Compliant row in the selected period (one month: that month; several months: non-compliant in any of them).',
    app_month.applications_without_completed_test AS COUNT(DISTINCT IFF(app_month.HAS_NO_COMPLETED_TEST = 1, app_month.EON_ID, NULL))
      WITH SYNONYMS = ('apps with no completed test', 'untested applications')
      COMMENT = 'Distinct applications with no Test_Complete row in the selected period. For several months it counts applications that lacked a completed test in at least one month.',
    app_month.applications_with_failed_test AS COUNT(DISTINCT IFF(app_month.HAS_FAILED_TEST = 1, app_month.EON_ID, NULL))
      WITH SYNONYMS = ('apps with failed test', 'applications that failed testing')
      COMMENT = 'Distinct applications with at least one completed test whose result is Fail.',
    app_month.newly_non_compliant_applications AS COUNT(DISTINCT IFF(app_month.MOVEMENT_STATUS = 'NEWLY_NON_COMPLIANT', app_month.EON_ID, NULL))
      WITH SYNONYMS = ('newly non compliant', 'deteriorated applications', 'new non compliance')
      COMMENT = 'PROVISIONAL. Applications non-compliant this month but not non-compliant the immediately preceding month.',
    app_month.resolved_applications AS COUNT(DISTINCT IFF(app_month.MOVEMENT_STATUS = 'RESOLVED', app_month.EON_ID, NULL))
      WITH SYNONYMS = ('resolved non compliance', 'recovered applications', 'improved applications')
      COMMENT = 'PROVISIONAL. Applications non-compliant the immediately preceding month but not this month.',
    app_month.persistent_non_compliant_applications AS COUNT(DISTINCT IFF(app_month.MOVEMENT_STATUS = 'PERSISTENT_NON_COMPLIANT', app_month.EON_ID, NULL))
      COMMENT = 'PROVISIONAL. Applications non-compliant this month and the immediately preceding month.',
    app_month.non_compliant_application_share AS COUNT(DISTINCT IFF(app_month.IS_NON_COMPLIANT_APP = 1, app_month.EON_ID, NULL)) / NULLIF(COUNT(DISTINCT app_month.EON_ID), 0)
      WITH SYNONYMS = ('share of applications non compliant', 'non compliance rate')
      COMMENT = 'Non-compliant applications divided by applications reporting, for the selected period and slice. Application-level, not the provisional metric-row rate.',
    -- OPEN_FINDINGS is already one value per application-month on the view (MAX of TOTAL_RFB).
    -- It is not also declared as a fact: Snowflake rejected that fact because the view column is an aggregate.
    app_month.open_findings AS SUM(app_month.OPEN_FINDINGS)
      WITH SYNONYMS = ('open findings', 'findings', 'total findings', 'remediation items')
      COMMENT = 'PROVISIONAL. Sum over applications of the application-month findings value (TOTAL_RFB taken once per application-month). Valid for ONE month at a time: always filter to a single reporting month; never add across months.',
    app_month.average_metrics_per_application AS AVG(app_month.METRICS_REPORTED)
      COMMENT = 'Average number of distinct metrics reported per application-month.',
    -- ---- observation-level (metric rows; NOT application counts) ----
    obs.observation_rows AS COUNT(obs.METRIC_ID)
      WITH SYNONYMS = ('rows', 'records', 'observations', 'metric rows')
      COMMENT = 'Number of metric rows (application x metric x month). One application can contribute several rows.',
    obs.distinct_applications_observed AS COUNT(DISTINCT obs.EON_ID)
      COMMENT = 'Distinct applications among the selected metric rows. Use when slicing by metric, test or compliance attributes that live on the row.',
    obs.distinct_metrics AS COUNT(DISTINCT obs.METRIC_ID) COMMENT = 'Number of distinct metric ids in the selected rows.',
    obs.compliant_rows      AS COUNT_IF(obs.COMPLIANCE_STATUS = 'Compliant')      COMMENT = 'Rows with compliance status Compliant.',
    obs.non_compliant_rows  AS COUNT_IF(obs.COMPLIANCE_STATUS = 'Non_Compliant')  WITH SYNONYMS = ('non compliant records') COMMENT = 'Rows with compliance status Non_Compliant.',
    obs.pending_rows        AS COUNT_IF(obs.COMPLIANCE_STATUS = 'Pending')        COMMENT = 'Rows with compliance status Pending.',
    obs.not_applicable_rows AS COUNT_IF(obs.COMPLIANCE_STATUS = 'Not_Applicable') COMMENT = 'Rows with compliance status Not_Applicable.',
    obs.completed_test_rows AS COUNT_IF(obs.TEST_STATUS = 'Test_Complete') COMMENT = 'Rows with TEST_STATUS Test_Complete.',
    obs.no_test_rows        AS COUNT_IF(obs.TEST_STATUS = 'No_Test')       COMMENT = 'Rows with TEST_STATUS No_Test.',
    obs.pending_test_rows   AS COUNT_IF(obs.TEST_STATUS = 'Test_Pending')  COMMENT = 'Rows with TEST_STATUS Test_Pending.',
    obs.exempt_rows         AS COUNT_IF(obs.TEST_STATUS = 'Exempt')        COMMENT = 'Rows with TEST_STATUS Exempt.',
    obs.passed_test_rows    AS COUNT_IF(obs.TEST_STATUS = 'Test_Complete' AND obs.TEST_RESULT = 'Pass') COMMENT = 'Completed tests with result Pass.',
    obs.failed_test_rows    AS COUNT_IF(obs.TEST_STATUS = 'Test_Complete' AND obs.TEST_RESULT = 'Fail') WITH SYNONYMS = ('failed tests', 'test failures') COMMENT = 'Completed tests with result Fail.',
    obs.failed_test_rate    AS COUNT_IF(obs.TEST_STATUS = 'Test_Complete' AND obs.TEST_RESULT = 'Fail') / NULLIF(COUNT_IF(obs.TEST_STATUS = 'Test_Complete' AND obs.TEST_RESULT IS NOT NULL), 0)
      WITH SYNONYMS = ('test failure rate', 'fail rate')
      COMMENT = 'Failed completed tests divided by completed tests that have a result (Pass or Fail). Row-level, not application-level.',
    obs.numerator_total     AS SUM(obs.IS_NUMERATOR)   COMMENT = 'PROVISIONAL. Sum of IS_NUMERATOR. Show alongside denominator_total.',
    obs.denominator_total   AS SUM(obs.IS_DENOMINATOR) COMMENT = 'PROVISIONAL. Sum of IS_DENOMINATOR. Show alongside numerator_total.',
    obs.provisional_compliance_rate AS SUM(obs.IS_NUMERATOR) / NULLIF(SUM(obs.IS_DENOMINATOR), 0)
      WITH SYNONYMS = ('compliance rate', 'compliance percentage', 'compliance %')
      COMMENT = 'PROVISIONAL, NOT a confirmed client metric. SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR). The numerator/denominator rule is a generator assumption and the denominator scope can differ by metric. Always label it provisional and state the numerator and denominator; when comparing metrics, group by metric_id.',
    obs.row_level_findings  AS SUM(obs.RFB) WITH SYNONYMS = ('RFB total') COMMENT = 'PROVISIONAL. Sum of row-level RFB over the selected rows. Not the application findings total and not comparable with open_findings.',
    obs.system_rtc_rows     AS SUM(obs.SYSTEM_RTC) COMMENT = 'PROVISIONAL. Rows where SYSTEM_RTC = 1. Business meaning not supplied.'
  )
  COMMENT = 'Synthetic enterprise application compliance dataset (11,399 rows, 57 source columns, 1,500 applications, 24 metrics, 12 month-ends 2025-11-30 to 2026-10-31). Two organisation hierarchies. Several measures are PROVISIONAL because the client has not supplied formulas.'
  AI_SQL_GENERATION $$
You write SQL for a compliance and technology-risk investigation analyst. This semantic view has two logical tables.
app_month = one row per application per month (application attributes and application-level flags). obs = one row per application, metric and month.
Rules you must follow:
1. Count applications with applications_reporting, non_compliant_applications, applications_without_completed_test, applications_with_failed_test or distinct_applications_observed. Never count obs rows as applications. Never use SUM of a row count as an application count.
2. Every question about "a month", "latest", "current" or "now" needs a reporting_month_end filter. The latest month is 2026-10-31. If the user gives no period, use the latest month and say so. For trends, group by reporting_month_end.
3. open_findings is valid for ONE month. Never add it across months. TOTAL_RFB repeats on every metric row of an application-month, so never sum it from obs rows.
4. "compliance rate" is not a confirmed metric. Use provisional_compliance_rate only when the user asks for a rate or percentage, call it provisional, and report numerator_total and denominator_total with it. Do not claim it is the client's compliance percentage. If comparing metrics, group by metric_id.
5. "Division", "department", "organisation" and "super division" mean hierarchy 2 (super_division, division, super_department, department). Use the bu_* columns only when the user says BU or business unit. Never mix the two hierarchies in one grouping. department is NULL for rows with org_group_type = SUPER_DEPARTMENT; group by super_department when you need every row.
6. Tier, risk code (P1-P4), ARR codes (A, C, I) and RTO bands have no severity direction. Never call tier 1 or P1 the highest or most critical. Show them as neutral labels and do not sort "most critical first".
7. "Deterioration", "got worse", "newly non-compliant" = movement_status NEWLY_NON_COMPLIANT (provisional: compares with the immediately preceding calendar month). "Improved" or "resolved" = RESOLVED.
8. "Failed testing" = TEST_STATUS Test_Complete and TEST_RESULT Fail. "No completed test" = no row with Test_Complete for that application in the period.
9. When both an application attribute (e.g. division) and a metric attribute (e.g. metric_id, compliance_reason) are needed, use obs metrics with the app_month dimension. Application-level metrics cannot be split by obs attributes; use distinct_applications_observed or non_compliant_rows with the obs dimension instead and say so.
10. Rank by counts only when asked; when comparing groups of different size also give the share. Include the denominator or population size.
11. Do not invent business definitions. If a question needs a definition the model does not hold (metric names, severity, targets, thresholds, SLAs), say it is not available.
$$
  AI_QUESTION_CATEGORIZATION $$
Answer questions about application compliance, testing, findings, organisation, legal entity, owners and reporting-period trends in this dataset.
Ask a clarifying question when: the user says "compliance rate" or "percentage" without accepting a provisional definition; "critical", "high risk" or "worst" is used (tier and risk codes have no severity direction); the period is unclear and the answer would differ by month; or "division"/"department" could mean the BU hierarchy.
Politely decline: questions about real companies, real people, regulations, thresholds, targets, SLAs, root causes not present in the data, forecasts, or anything outside this dataset. All names in the data are synthetic.
$$;

-- Checkpoint 12
DESCRIBE SEMANTIC VIEW METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1;
-- Expected: two logical tables (APP_MONTH, OBS), one relationship (OBS_TO_APP_MONTH), the facts, dimensions and metrics above.
SHOW SEMANTIC VIEWS IN SCHEMA METRICS_ANALYZER.MOCK_DATA;       -- Expected: SV_APPLICATION_COMPLIANCE_V1
SHOW SEMANTIC DIMENSIONS IN METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1;
SHOW SEMANTIC METRICS IN METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1;
-- If CREATE SEMANTIC VIEW fails with a syntax error, STOP. Capture the full error text and the line it points to.
-- The most likely adjustments (account feature differences, see SEMANTIC_MODEL.md "Syntax risk list") are listed there.
