-- =====================================================================================
-- 04_validate_staged_file.sql
-- Run AFTER uploading synthetic_enterprise_data.csv to @CLIENT_DATA_STAGE (README step 5).
-- Nothing is loaded here. The only object created is a scratch table that is dropped at the end.
-- Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = 'ACCOUNTADMIN';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = 'COMPUTE_WH';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 4.1 Is the file there?
LIST @CLIENT_DATA_STAGE;
-- Expected: exactly one file, name ending in synthetic_enterprise_data.csv, size about 6,701,793 bytes
--           (Snowsight may show the file gzip-compressed as .csv.gz with a smaller size; both are fine as long as
--            the name matches. Use the exact name shown in the "name" column in script 05.)
-- STOP if: no file, two files, or a different name (a leftover from an earlier upload would load twice).

-- 4.2 Header check. Compares each header cell with the expected name in the expected position.
SELECT
    IFF($1 = 'METRIC_ID', 1, 0) +
    IFF($2 = 'METRIC_DATE', 1, 0) +
    IFF($3 = 'METRIC_DATE_TYPE', 1, 0) +
    IFF($4 = 'IS_NUMERATOR', 1, 0) +
    IFF($5 = 'IS_DENOMINATOR', 1, 0) +
    IFF($6 = 'EON_ID', 1, 0) +
    IFF($7 = 'BUILDING_NAME', 1, 0) +
    IFF($8 = 'EVENT_LOCATION', 1, 0) +
    IFF($9 = 'APPLICATION_TIER', 1, 0) +
    IFF($10 = 'EXEMPTION_LEVEL_1', 1, 0) +
    IFF($11 = 'TEST_STATUS', 1, 0) +
    IFF($12 = 'TEST_RESULT', 1, 0) +
    IFF($13 = 'SYSTEM_RTC', 1, 0) +
    IFF($14 = 'RFB', 1, 0) +
    IFF($15 = 'TOTAL_RFB', 1, 0) +
    IFF($16 = 'COMPLIANCE_STATUS', 1, 0) +
    IFF($17 = 'COMPLIANCE_REASON', 1, 0) +
    IFF($18 = 'RTO_CHANGE_DATE', 1, 0) +
    IFF($19 = 'GRN', 1, 0) +
    IFF($20 = 'APPLICATION_NAME', 1, 0) +
    IFF($21 = 'APPLICATION_RTO', 1, 0) +
    IFF($22 = 'HAS_CTIRICAL_KBS', 1, 0) +
    IFF($23 = 'LIFECYCLE_PHASE', 1, 0) +
    IFF($24 = 'ASSET_RISK_RATING_2', 1, 0) +
    IFF($25 = 'ARR_AVAILABILITY', 1, 0) +
    IFF($26 = 'ARR_CONFIDENTIALITY', 1, 0) +
    IFF($27 = 'ARR_INTEGRITY', 1, 0) +
    IFF($28 = 'IS_MERGERS_ACQUISITIONS_ASSET', 1, 0) +
    IFF($29 = 'ACQUIRED_ENTITY', 1, 0) +
    IFF($30 = 'BU_SUPER_DIVISION', 1, 0) +
    IFF($31 = 'BU_DIVISION', 1, 0) +
    IFF($32 = 'BU_SUPER_DEPARTMENT', 1, 0) +
    IFF($33 = 'BU_DEPARTMENT', 1, 0) +
    IFF($34 = 'ORG_GROUP_TYPE', 1, 0) +
    IFF($35 = 'SUPER_DIVISION', 1, 0) +
    IFF($36 = 'DIVISION', 1, 0) +
    IFF($37 = 'SUPER_DEPARTMENT', 1, 0) +
    IFF($38 = 'DEPARTMENT', 1, 0) +
    IFF($39 = 'BUS_ORG_LG_NM', 1, 0) +
    IFF($40 = 'COST_CENTER_CODE', 1, 0) +
    IFF($41 = 'COST_CENTER_NAME', 1, 0) +
    IFF($42 = 'EMPLOYEE_BUILDING_NAME', 1, 0) +
    IFF($43 = 'EMPLOYEE_COUNTRY_NAME', 1, 0) +
    IFF($44 = 'PRIMARY_BUS_FIRST_NAME', 1, 0) +
    IFF($45 = 'PRIMARY_BUS_LAST_NAME', 1, 0) +
    IFF($46 = 'PRIMARY_IT_FIRST_NAME', 1, 0) +
    IFF($47 = 'PRIMARY_IT_LAST_NAME', 1, 0) +
    IFF($48 = 'LEGAL_ENTITY_CODE', 1, 0) +
    IFF($49 = 'LEGAL_ENTITY_NAME', 1, 0) +
    IFF($50 = 'IS_USBANKS', 1, 0) +
    IFF($51 = 'IS_MSBNA', 1, 0) +
    IFF($52 = 'IS_MSPBNA', 1, 0) +
    IFF($53 = 'USBANKS_LE_LIST', 1, 0) +
    IFF($54 = 'KBS_FLAG_FLAG', 1, 0) +
    IFF($55 = 'REPORTING_MONTHEND_DATE', 1, 0) +
    IFF($56 = 'REPORTING_MONTH', 1, 0) +
    IFF($57 = 'REPORTING_YEAR', 1, 0)
    AS matching_header_cells,
    57 AS expected
FROM @CLIENT_DATA_STAGE/synthetic_enterprise_data.csv
     (FILE_FORMAT => 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT_NOHEADER')
LIMIT 1;
-- Expected: matching_header_cells = 57. Anything less: the column order or a name differs. STOP and capture the output.
-- (If your staged file is compressed, use the same path; Snowflake reads .gz transparently.)

-- 4.3 Row count, field-count shape, delimiter sanity, date shape, null handling.
SELECT
    COUNT(*)                                                            AS data_rows,                -- Expected 11399
    COUNT_IF($58 IS NOT NULL)                                           AS rows_with_extra_fields,   -- Expected 0 (more than 57 fields)
    COUNT_IF($57 IS NULL)                                               AS rows_missing_last_field,  -- Expected 0 (REPORTING_YEAR is never blank)
    COUNT_IF($2 NOT RLIKE '[0-9]{4}-[0-9]{2}-[0-9]{2}')                 AS bad_metric_date_shape,    -- Expected 0
    COUNT_IF($55 NOT RLIKE '[0-9]{4}-[0-9]{2}-[0-9]{2}')                AS bad_reporting_date_shape, -- Expected 0
    COUNT_IF($12 IS NULL)                                               AS blank_test_result,        -- Expected 3888 (blank = NULL)
    COUNT_IF($10 IS NULL)                                               AS blank_exemption_level,    -- Expected 10254
    COUNT(DISTINCT $6)                                                  AS distinct_eon_id,          -- Expected 1500
    COUNT(DISTINCT $1)                                                  AS distinct_metric_id        -- Expected 24
FROM @CLIENT_DATA_STAGE/synthetic_enterprise_data.csv
     (FILE_FORMAT => 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT');

-- 4.4 Eyeball five rows.
SELECT $1 AS metric_id, $2 AS metric_date, $6 AS eon_id, $11 AS test_status, $12 AS test_result,
       $16 AS compliance_status, $55 AS reporting_monthend_date
FROM @CLIENT_DATA_STAGE/synthetic_enterprise_data.csv
     (FILE_FORMAT => 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT')
LIMIT 5;

-- 4.5 Snowflake parse validation WITHOUT loading (COPY ... VALIDATION_MODE). Uses a throw-away scratch table with
--     exactly 57 text columns because VALIDATION_MODE does not allow a COPY that transforms data (script 05 does).
CREATE OR REPLACE TRANSIENT TABLE RAW_PARSE_CHECK_TMP (
    METRIC_ID VARCHAR,
    METRIC_DATE VARCHAR,
    METRIC_DATE_TYPE VARCHAR,
    IS_NUMERATOR VARCHAR,
    IS_DENOMINATOR VARCHAR,
    EON_ID VARCHAR,
    BUILDING_NAME VARCHAR,
    EVENT_LOCATION VARCHAR,
    APPLICATION_TIER VARCHAR,
    EXEMPTION_LEVEL_1 VARCHAR,
    TEST_STATUS VARCHAR,
    TEST_RESULT VARCHAR,
    SYSTEM_RTC VARCHAR,
    RFB VARCHAR,
    TOTAL_RFB VARCHAR,
    COMPLIANCE_STATUS VARCHAR,
    COMPLIANCE_REASON VARCHAR,
    RTO_CHANGE_DATE VARCHAR,
    GRN VARCHAR,
    APPLICATION_NAME VARCHAR,
    APPLICATION_RTO VARCHAR,
    HAS_CTIRICAL_KBS VARCHAR,
    LIFECYCLE_PHASE VARCHAR,
    ASSET_RISK_RATING_2 VARCHAR,
    ARR_AVAILABILITY VARCHAR,
    ARR_CONFIDENTIALITY VARCHAR,
    ARR_INTEGRITY VARCHAR,
    IS_MERGERS_ACQUISITIONS_ASSET VARCHAR,
    ACQUIRED_ENTITY VARCHAR,
    BU_SUPER_DIVISION VARCHAR,
    BU_DIVISION VARCHAR,
    BU_SUPER_DEPARTMENT VARCHAR,
    BU_DEPARTMENT VARCHAR,
    ORG_GROUP_TYPE VARCHAR,
    SUPER_DIVISION VARCHAR,
    DIVISION VARCHAR,
    SUPER_DEPARTMENT VARCHAR,
    DEPARTMENT VARCHAR,
    BUS_ORG_LG_NM VARCHAR,
    COST_CENTER_CODE VARCHAR,
    COST_CENTER_NAME VARCHAR,
    EMPLOYEE_BUILDING_NAME VARCHAR,
    EMPLOYEE_COUNTRY_NAME VARCHAR,
    PRIMARY_BUS_FIRST_NAME VARCHAR,
    PRIMARY_BUS_LAST_NAME VARCHAR,
    PRIMARY_IT_FIRST_NAME VARCHAR,
    PRIMARY_IT_LAST_NAME VARCHAR,
    LEGAL_ENTITY_CODE VARCHAR,
    LEGAL_ENTITY_NAME VARCHAR,
    IS_USBANKS VARCHAR,
    IS_MSBNA VARCHAR,
    IS_MSPBNA VARCHAR,
    USBANKS_LE_LIST VARCHAR,
    KBS_FLAG_FLAG VARCHAR,
    REPORTING_MONTHEND_DATE VARCHAR,
    REPORTING_MONTH VARCHAR,
    REPORTING_YEAR VARCHAR
);

COPY INTO RAW_PARSE_CHECK_TMP
FROM @CLIENT_DATA_STAGE/synthetic_enterprise_data.csv
FILE_FORMAT = (FORMAT_NAME = 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT')
VALIDATION_MODE = RETURN_ERRORS;
-- Expected: zero rows returned (no parse errors). Any returned row = a parse problem: STOP, capture the rows.

SELECT COUNT(*) AS scratch_rows FROM RAW_PARSE_CHECK_TMP;  -- Expected 0 (validation mode loads nothing)

DROP TABLE IF EXISTS RAW_PARSE_CHECK_TMP;

-- Checkpoint 04 passed when: one correctly named file, matching_header_cells = 57, data_rows = 11399,
-- all "Expected 0" columns are 0, and RETURN_ERRORS returned nothing.
