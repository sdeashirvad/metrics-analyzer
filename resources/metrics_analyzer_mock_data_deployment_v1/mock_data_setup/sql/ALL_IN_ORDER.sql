-- Concatenation of scripts 00-15 for convenience. UNEXECUTED. Run script by script the first time.
-- Each section repeats the SET/USE header: edit <SETUP_ROLE> and <WAREHOUSE_NAME> in every section (or search/replace once).
-- The CSV must be uploaded to the stage (README step 5) between scripts 03 and 04.


-- ##################### 00_preflight.sql #####################
-- =====================================================================================
-- 00_preflight.sql   READ-ONLY. Creates nothing, changes nothing.
-- Purpose : discover the account facts you must supply before running scripts 01-15.
-- Run as  : the role you intend to use for setup (or any role that can see the objects).
-- Status  : UNEXECUTED. Written from Snowflake documentation, not tested on your account.
-- =====================================================================================

-- 0.1 Who am I, where am I?
SELECT CURRENT_ACCOUNT()  AS account_locator,
       CURRENT_REGION()   AS region,
       CURRENT_USER()     AS user_name,
       CURRENT_ROLE()     AS current_role,
       CURRENT_WAREHOUSE() AS current_warehouse,
       CURRENT_DATABASE() AS current_database,
       CURRENT_SCHEMA()   AS current_schema;

-- 0.2 Which warehouse do I use?  Pick the EXISTING warehouse your team already uses for the DQ agent.
--     Copy its exact name from the "name" column. This is your <WAREHOUSE_NAME>.
SHOW WAREHOUSES;

-- 0.3 Which roles do I hold?  Your <SETUP_ROLE> must be able to create a schema in METRICS_ANALYZER.
SELECT CURRENT_AVAILABLE_ROLES() AS roles_i_can_use;

-- 0.4 Does the target database exist, and who may create schemas in it?
SHOW DATABASES LIKE 'METRICS_ANALYZER';
SHOW GRANTS ON DATABASE METRICS_ANALYZER;
--     Look for a role holding OWNERSHIP, or USAGE plus CREATE SCHEMA. That role is a valid <SETUP_ROLE>.

-- 0.5 Existing schemas. DQ must be present and is NEVER touched by this package.
SHOW SCHEMAS IN DATABASE METRICS_ANALYZER;
--     Expected: DQ is listed. MOCK_DATA should NOT be listed yet (script 01 creates it).
--     If MOCK_DATA already exists, stop and read the README troubleshooting section before continuing.

-- 0.6 Existing DQ objects, listed only so you can confirm they are not in scope. Read-only.
SHOW STAGES IN SCHEMA METRICS_ANALYZER.DQ;
SHOW FILE FORMATS IN SCHEMA METRICS_ANALYZER.DQ;
SHOW AGENTS IN SCHEMA METRICS_ANALYZER.DQ;

-- 0.7 Viewer role used in script 14.
SHOW ROLES LIKE 'METRICS_ANALYZER_DEMO_VIEWER';
--     Expected: one row. If none, ask your administrator; this package does not create roles.

-- 0.8 Cortex availability and cross-region inference.
--     Cortex Analyst / Agents run models that may live in another region.
--     Account parameter CORTEX_ENABLED_CROSS_REGION controls whether the account may call them.
SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;
--     Value 'DISABLED' (or empty) and your region does not host the models  ->  see the
--     CONDITIONAL ADMINISTRATOR STEP in PERMISSIONS.md. Do NOT change it from this package.

-- 0.9 Cortex database roles. SNOWFLAKE.CORTEX_USER is granted to PUBLIC by default.
SHOW DATABASE ROLES IN DATABASE SNOWFLAKE;
SHOW GRANTS OF DATABASE ROLE SNOWFLAKE.CORTEX_USER;
SHOW GRANTS OF DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER;
--     If PUBLIC appears under CORTEX_USER, the viewer role already has Cortex access and script 14
--     section B can be skipped. If not, script 14 section B grants CORTEX_AGENT_USER to the viewer role.

-- 0.10 Can my role create the objects? Run each as the setup role; every row should show your role as grantee.
SET CURRENT_ROLE_NAME = CURRENT_ROLE();
SHOW GRANTS TO ROLE IDENTIFIER($CURRENT_ROLE_NAME);
--     Needed in MOCK_DATA after script 01: ownership of the schema covers CREATE TABLE/VIEW/STAGE/
--     FILE FORMAT/SEMANTIC VIEW/AGENT because the creating role owns the schema it creates.
--     Needed before script 01: CREATE SCHEMA on METRICS_ANALYZER.

-- 0.11 Stop here. Write down:  <SETUP_ROLE>, <WAREHOUSE_NAME>, region, cross-region value, CORTEX_USER grantees.


-- ##################### 01_create_schema.sql #####################
-- =====================================================================================
-- 01_create_schema.sql
-- Creates ONLY METRICS_ANALYZER.MOCK_DATA. Never touches METRICS_ANALYZER.DQ.
-- Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;

CREATE SCHEMA IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA
  COMMENT = 'Synthetic enterprise application compliance dataset (seed 20261103) for Cortex Analyst and the Application Compliance agent. Separate from the DQ schema.';

USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- Checkpoint 01
-- Expected: two rows, DQ and MOCK_DATA (plus INFORMATION_SCHEMA and any others you already had).
SHOW SCHEMAS IN DATABASE METRICS_ANALYZER;
-- Expected: MOCK_DATA owner = your setup role.
-- If CREATE SCHEMA failed with insufficient privileges: STOP. Capture the error and the output of 00_preflight section 0.4.


-- ##################### 02_create_file_format_and_stage.sql #####################
-- =====================================================================================
-- 02_create_file_format_and_stage.sql
-- Named CSV file format + named internal stage. No external storage, no Snowpipe.
-- Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- Primary file format used by COPY INTO. Matches the generated CSV:
--   comma delimiter, LF record delimiter, one header row, no quoted fields in the current file
--   (optional enclosure kept so a re-export with quotes still loads), blank field = NULL, UTF-8, ISO dates (kept as text in raw).
CREATE FILE FORMAT IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT
  TYPE = CSV
  FIELD_DELIMITER = ','
  RECORD_DELIMITER = '\n'
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('')
  EMPTY_FIELD_AS_NULL = TRUE
  TRIM_SPACE = FALSE
  ERROR_ON_COLUMN_COUNT_MISMATCH = TRUE
  ENCODING = 'UTF8'
  COMMENT = 'Generated application compliance CSV: header row, comma delimited, blank = NULL.';

-- Helper format used ONLY by script 04 to read the header row as data (SKIP_HEADER = 0).
CREATE FILE FORMAT IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT_NOHEADER
  TYPE = CSV
  FIELD_DELIMITER = ','
  RECORD_DELIMITER = '\n'
  SKIP_HEADER = 0
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('')
  EMPTY_FIELD_AS_NULL = TRUE
  TRIM_SPACE = FALSE
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
  ENCODING = 'UTF8'
  COMMENT = 'Header-inspection helper. Not used for loading.';

-- Named internal stage. SNOWFLAKE_SSE encryption lets Snowsight preview staged files.
CREATE STAGE IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.CLIENT_DATA_STAGE
  FILE_FORMAT = (FORMAT_NAME = 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT')
  DIRECTORY = (ENABLE = TRUE)
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
  COMMENT = 'Landing stage for the synthetic application compliance CSV.';

-- Checkpoint 02
SHOW FILE FORMATS IN SCHEMA METRICS_ANALYZER.MOCK_DATA;   -- Expected: CLIENT_CSV_FORMAT, CLIENT_CSV_FORMAT_NOHEADER
SHOW STAGES       IN SCHEMA METRICS_ANALYZER.MOCK_DATA;   -- Expected: CLIENT_DATA_STAGE
LIST @METRICS_ANALYZER.MOCK_DATA.CLIENT_DATA_STAGE;       -- Expected: empty (upload happens next, via Snowsight; see README step 5)


-- ##################### 03_create_raw_tables.sql #####################
-- =====================================================================================
-- 03_create_raw_tables.sql
-- Raw landing table + the two operational tables (load audit, rejected rows).
-- All CREATE ... IF NOT EXISTS: re-running never drops or empties loaded data.
-- Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- One row per load attempt. Statuses advance:
--   STARTED > RAW_LOADED > STAGED > VALIDATED > PROMOTED > RECONCILED   (or FAILED / RECONCILED_WITH_REJECTS)
CREATE TABLE IF NOT EXISTS DATASET_LOAD_AUDIT (
    LOAD_BATCH_ID        VARCHAR       NOT NULL,
    DATASET_VERSION      VARCHAR       NOT NULL,
    SOURCE_FILE_NAME     VARCHAR       NOT NULL,
    SOURCE_FILE_SHA256   VARCHAR,
    EXPECTED_ROWS        NUMBER(10,0)  NOT NULL,
    EXPECTED_COLUMNS     NUMBER(4,0)   NOT NULL,
    ROWS_RAW             NUMBER(10,0),
    ROWS_STG             NUMBER(10,0),
    ROWS_FINAL           NUMBER(10,0),
    ROWS_REJECTED        NUMBER(10,0),
    STATUS               VARCHAR       NOT NULL,
    NOTES                VARCHAR,
    CREATED_AT           TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT           TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'One row per load batch of the synthetic application compliance dataset.';

-- Rows that fail type conversion or a row-level validation rule. Never silently dropped.
CREATE TABLE IF NOT EXISTS DATASET_REJECTED_ROWS (
    LOAD_BATCH_ID           VARCHAR  NOT NULL,
    SOURCE_FILE_ROW_NUMBER  NUMBER(10,0),
    EON_ID                  VARCHAR,
    METRIC_ID               VARCHAR,
    METRIC_DATE_RAW         VARCHAR,
    REJECT_REASONS          ARRAY    NOT NULL,
    RAW_RECORD              OBJECT,
    REJECTED_AT             TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Quarantine for rows that failed conversion or row-level validation, with reasons.';

-- Raw landing: the 57 source columns exactly as supplied (all VARCHAR; blank CSV field = NULL),
-- followed by 4 ingestion-metadata columns. The metadata columns are NOT part of the client specification.
CREATE TABLE IF NOT EXISTS RAW_APPLICATION_COMPLIANCE (
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
    REPORTING_YEAR VARCHAR,
    -- ingestion metadata (not source columns)
    SOURCE_FILE_NAME        VARCHAR,
    SOURCE_FILE_ROW_NUMBER  NUMBER(10,0),
    LOAD_BATCH_ID           VARCHAR,
    LOADED_AT               TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Raw landing of synthetic_enterprise_data.csv. 57 source columns as VARCHAR plus 4 ingestion metadata columns.';

-- Checkpoint 03
SHOW TABLES IN SCHEMA METRICS_ANALYZER.MOCK_DATA;
-- Expected: DATASET_LOAD_AUDIT, DATASET_REJECTED_ROWS, RAW_APPLICATION_COMPLIANCE.
SELECT COUNT(*) AS raw_columns_incl_metadata
FROM METRICS_ANALYZER.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'MOCK_DATA' AND TABLE_NAME = 'RAW_APPLICATION_COMPLIANCE';
-- Expected: 61  (57 source + 4 metadata)
SELECT COUNT(*) AS raw_rows FROM RAW_APPLICATION_COMPLIANCE;
-- Expected: 0 on first run.


-- ##################### 04_validate_staged_file.sql #####################
-- =====================================================================================
-- 04_validate_staged_file.sql
-- Run AFTER uploading synthetic_enterprise_data.csv to @CLIENT_DATA_STAGE (README step 5).
-- Nothing is loaded here. The only object created is a scratch table that is dropped at the end.
-- Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
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


-- ##################### 05_copy_into_raw.sql #####################
-- =====================================================================================
-- 05_copy_into_raw.sql
-- Loads the authoritative CSV into RAW_APPLICATION_COMPLIANCE and opens the audit record.
-- No FORCE option. No silent double load. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- Batch identity. Change BOTH values together when you load a new version (see "Reloading a changed dataset" below).
--   batch id      : MOCK_V1_20261103
--   file in stage : synthetic_enterprise_data.csv   (use the exact name shown by LIST in script 04)

-- 5.1 Idempotency guard. Both numbers must be 0 before you continue.
SELECT
    (SELECT COUNT(*) FROM DATASET_LOAD_AUDIT WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103')           AS audit_rows_for_batch,   -- Expected 0
    (SELECT COUNT(*) FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103')   AS raw_rows_for_batch;     -- Expected 0
-- If either is not 0 this batch was already (partly) loaded. STOP. Do not rerun COPY. See README, "Troubleshooting".

-- 5.2 Open the audit record (inserts only when the batch is new).
INSERT INTO DATASET_LOAD_AUDIT (LOAD_BATCH_ID, DATASET_VERSION, SOURCE_FILE_NAME, SOURCE_FILE_SHA256,
                                EXPECTED_ROWS, EXPECTED_COLUMNS, STATUS, NOTES)
SELECT 'MOCK_V1_20261103', 'v1-seed20261103', 'synthetic_enterprise_data.csv',
       '08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3',
       11399, 57, 'STARTED', 'SHA-256 is the value from MANIFEST.txt for the CSV you uploaded.'
WHERE NOT EXISTS (SELECT 1 FROM DATASET_LOAD_AUDIT WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103');

-- 5.3 Load. ON_ERROR = ABORT_STATEMENT makes the load all-or-nothing: one bad row and nothing is loaded.
--     Explicit column list: the 57 source columns map to $1..$57 by position; metadata comes from METADATA$ columns.
COPY INTO RAW_APPLICATION_COMPLIANCE (
    METRIC_ID, METRIC_DATE, METRIC_DATE_TYPE, IS_NUMERATOR,
    IS_DENOMINATOR, EON_ID, BUILDING_NAME, EVENT_LOCATION,
    APPLICATION_TIER, EXEMPTION_LEVEL_1, TEST_STATUS, TEST_RESULT,
    SYSTEM_RTC, RFB, TOTAL_RFB, COMPLIANCE_STATUS,
    COMPLIANCE_REASON, RTO_CHANGE_DATE, GRN, APPLICATION_NAME,
    APPLICATION_RTO, HAS_CTIRICAL_KBS, LIFECYCLE_PHASE, ASSET_RISK_RATING_2,
    ARR_AVAILABILITY, ARR_CONFIDENTIALITY, ARR_INTEGRITY, IS_MERGERS_ACQUISITIONS_ASSET,
    ACQUIRED_ENTITY, BU_SUPER_DIVISION, BU_DIVISION, BU_SUPER_DEPARTMENT,
    BU_DEPARTMENT, ORG_GROUP_TYPE, SUPER_DIVISION, DIVISION,
    SUPER_DEPARTMENT, DEPARTMENT, BUS_ORG_LG_NM, COST_CENTER_CODE,
    COST_CENTER_NAME, EMPLOYEE_BUILDING_NAME, EMPLOYEE_COUNTRY_NAME, PRIMARY_BUS_FIRST_NAME,
    PRIMARY_BUS_LAST_NAME, PRIMARY_IT_FIRST_NAME, PRIMARY_IT_LAST_NAME, LEGAL_ENTITY_CODE,
    LEGAL_ENTITY_NAME, IS_USBANKS, IS_MSBNA, IS_MSPBNA,
    USBANKS_LE_LIST, KBS_FLAG_FLAG, REPORTING_MONTHEND_DATE, REPORTING_MONTH,
    REPORTING_YEAR,
    SOURCE_FILE_NAME, SOURCE_FILE_ROW_NUMBER, LOAD_BATCH_ID
)
FROM (
    SELECT
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24,
    $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36,
    $37, $38, $39, $40, $41, $42, $43, $44, $45, $46, $47, $48,
    $49, $50, $51, $52, $53, $54, $55, $56, $57,
    METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, 'MOCK_V1_20261103'
    FROM @CLIENT_DATA_STAGE
)
FILES = ('synthetic_enterprise_data.csv')
FILE_FORMAT = (FORMAT_NAME = 'METRICS_ANALYZER.MOCK_DATA.CLIENT_CSV_FORMAT')
ON_ERROR = ABORT_STATEMENT
PURGE = FALSE;
-- Expected result row: file name, status LOADED, rows_parsed 11399, rows_loaded 11399, errors_seen 0.
-- If the stage shows the file as synthetic_enterprise_data.csv.gz, put that exact name in FILES = (...).
-- If COPY says "Copy executed with 0 files processed", Snowflake already has load metadata for that file name:
-- the file was loaded before. Do NOT add FORCE = TRUE. Use a new versioned file name instead (see below).

-- 5.4 Checkpoint 05
SELECT COUNT(*)                           AS raw_rows,               -- Expected 11399
       COUNT(DISTINCT SOURCE_FILE_ROW_NUMBER) AS distinct_file_rows, -- Expected 11399
       COUNT(DISTINCT SOURCE_FILE_NAME)   AS distinct_files,         -- Expected 1
       MIN(SOURCE_FILE_ROW_NUMBER)        AS first_file_row,         -- Expected 2 (header is file row 1) - note the value you see
       COUNT_IF(EON_ID IS NULL OR METRIC_ID IS NULL) AS missing_keys -- Expected 0
FROM RAW_APPLICATION_COMPLIANCE
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103';

UPDATE DATASET_LOAD_AUDIT
SET ROWS_RAW = (SELECT COUNT(*) FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
    STATUS = 'RAW_LOADED', UPDATED_AT = CURRENT_TIMESTAMP()
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND STATUS = 'STARTED'
  AND (SELECT COUNT(*) FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') = 11399;
-- Expected: 1 row updated. 0 rows updated means the raw count is not 11399: STOP and capture the 5.4 output.

-- ---- Reloading a changed dataset (read before ever loading a second version) -------------------------------------
-- 1. Save the new CSV under a NEW name, e.g. synthetic_enterprise_data_v2.csv, and upload it to the same stage.
-- 2. Choose a new batch id (e.g. MOCK_V2_<date>) and a new DATASET_VERSION in 5.1, 5.2 and 5.3.
-- 3. The downstream scripts are guarded per batch id; decide explicitly (and record in the audit NOTES) whether
--    the new batch replaces or sits beside the old one before promoting it. Never use FORCE = TRUE as a shortcut.


-- ##################### 06_create_typed_staging.sql #####################
-- =====================================================================================
-- 06_create_typed_staging.sql
-- Typed staging: converts the 57 raw VARCHAR columns to the data-dictionary types, keeping a trace to the raw row.
-- Conversion failures are recorded in CONVERSION_ERRORS (not discarded). Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

CREATE TABLE IF NOT EXISTS STG_APPLICATION_COMPLIANCE (
    METRIC_ID VARCHAR(20),
    METRIC_DATE DATE,
    METRIC_DATE_TYPE VARCHAR(20),
    IS_NUMERATOR NUMBER(1,0),
    IS_DENOMINATOR NUMBER(1,0),
    EON_ID VARCHAR(20),
    BUILDING_NAME VARCHAR(50),
    EVENT_LOCATION VARCHAR(50),
    APPLICATION_TIER NUMBER(1,0),
    EXEMPTION_LEVEL_1 VARCHAR(50),
    TEST_STATUS VARCHAR(30),
    TEST_RESULT VARCHAR(20),
    SYSTEM_RTC NUMBER(1,0),
    RFB NUMBER(10,0),
    TOTAL_RFB NUMBER(10,0),
    COMPLIANCE_STATUS VARCHAR(30),
    COMPLIANCE_REASON VARCHAR(60),
    RTO_CHANGE_DATE DATE,
    GRN VARCHAR(100),
    APPLICATION_NAME VARCHAR(100),
    APPLICATION_RTO VARCHAR(30),
    HAS_CTIRICAL_KBS VARCHAR(1),
    LIFECYCLE_PHASE VARCHAR(30),
    ASSET_RISK_RATING_2 VARCHAR(10),
    ARR_AVAILABILITY VARCHAR(10),
    ARR_CONFIDENTIALITY VARCHAR(10),
    ARR_INTEGRITY VARCHAR(10),
    IS_MERGERS_ACQUISITIONS_ASSET VARCHAR(1),
    ACQUIRED_ENTITY VARCHAR(60),
    BU_SUPER_DIVISION VARCHAR(100),
    BU_DIVISION VARCHAR(100),
    BU_SUPER_DEPARTMENT VARCHAR(100),
    BU_DEPARTMENT VARCHAR(100),
    ORG_GROUP_TYPE VARCHAR(30),
    SUPER_DIVISION VARCHAR(100),
    DIVISION VARCHAR(100),
    SUPER_DEPARTMENT VARCHAR(100),
    DEPARTMENT VARCHAR(100),
    BUS_ORG_LG_NM VARCHAR(100),
    COST_CENTER_CODE VARCHAR(20),
    COST_CENTER_NAME VARCHAR(100),
    EMPLOYEE_BUILDING_NAME VARCHAR(50),
    EMPLOYEE_COUNTRY_NAME VARCHAR(50),
    PRIMARY_BUS_FIRST_NAME VARCHAR(100),
    PRIMARY_BUS_LAST_NAME VARCHAR(100),
    PRIMARY_IT_FIRST_NAME VARCHAR(100),
    PRIMARY_IT_LAST_NAME VARCHAR(100),
    LEGAL_ENTITY_CODE VARCHAR(20),
    LEGAL_ENTITY_NAME VARCHAR(100),
    IS_USBANKS VARCHAR(1),
    IS_MSBNA VARCHAR(1),
    IS_MSPBNA VARCHAR(1),
    USBANKS_LE_LIST VARCHAR(50),
    KBS_FLAG_FLAG VARCHAR(1),
    REPORTING_MONTHEND_DATE DATE,
    REPORTING_MONTH NUMBER(2,0),
    REPORTING_YEAR NUMBER(4,0),
    -- traceability + conversion result (not source columns)
    LOAD_BATCH_ID           VARCHAR,
    SOURCE_FILE_ROW_NUMBER  NUMBER(10,0),
    CONVERSION_ERRORS       ARRAY,
    STAGED_AT               TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Typed copy of the raw rows. CONVERSION_ERRORS lists columns whose raw text could not be converted.';

-- Explicit column mapping, in source order. Dates must look like YYYY-MM-DD; numbers must be whole non-negative digits.
INSERT INTO STG_APPLICATION_COMPLIANCE (
    METRIC_ID, METRIC_DATE, METRIC_DATE_TYPE, IS_NUMERATOR,
    IS_DENOMINATOR, EON_ID, BUILDING_NAME, EVENT_LOCATION,
    APPLICATION_TIER, EXEMPTION_LEVEL_1, TEST_STATUS, TEST_RESULT,
    SYSTEM_RTC, RFB, TOTAL_RFB, COMPLIANCE_STATUS,
    COMPLIANCE_REASON, RTO_CHANGE_DATE, GRN, APPLICATION_NAME,
    APPLICATION_RTO, HAS_CTIRICAL_KBS, LIFECYCLE_PHASE, ASSET_RISK_RATING_2,
    ARR_AVAILABILITY, ARR_CONFIDENTIALITY, ARR_INTEGRITY, IS_MERGERS_ACQUISITIONS_ASSET,
    ACQUIRED_ENTITY, BU_SUPER_DIVISION, BU_DIVISION, BU_SUPER_DEPARTMENT,
    BU_DEPARTMENT, ORG_GROUP_TYPE, SUPER_DIVISION, DIVISION,
    SUPER_DEPARTMENT, DEPARTMENT, BUS_ORG_LG_NM, COST_CENTER_CODE,
    COST_CENTER_NAME, EMPLOYEE_BUILDING_NAME, EMPLOYEE_COUNTRY_NAME, PRIMARY_BUS_FIRST_NAME,
    PRIMARY_BUS_LAST_NAME, PRIMARY_IT_FIRST_NAME, PRIMARY_IT_LAST_NAME, LEGAL_ENTITY_CODE,
    LEGAL_ENTITY_NAME, IS_USBANKS, IS_MSBNA, IS_MSPBNA,
    USBANKS_LE_LIST, KBS_FLAG_FLAG, REPORTING_MONTHEND_DATE, REPORTING_MONTH,
    REPORTING_YEAR,
    LOAD_BATCH_ID, SOURCE_FILE_ROW_NUMBER, CONVERSION_ERRORS
)
SELECT
    r.METRIC_ID,
    IFF(REGEXP_LIKE(r.METRIC_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.METRIC_DATE, 'YYYY-MM-DD'), NULL),
    r.METRIC_DATE_TYPE,
    IFF(REGEXP_LIKE(r.IS_NUMERATOR, '[0-9]+'), TRY_TO_NUMBER(r.IS_NUMERATOR), NULL),
    IFF(REGEXP_LIKE(r.IS_DENOMINATOR, '[0-9]+'), TRY_TO_NUMBER(r.IS_DENOMINATOR), NULL),
    r.EON_ID,
    r.BUILDING_NAME,
    r.EVENT_LOCATION,
    IFF(REGEXP_LIKE(r.APPLICATION_TIER, '[0-9]+'), TRY_TO_NUMBER(r.APPLICATION_TIER), NULL),
    r.EXEMPTION_LEVEL_1,
    r.TEST_STATUS,
    r.TEST_RESULT,
    IFF(REGEXP_LIKE(r.SYSTEM_RTC, '[0-9]+'), TRY_TO_NUMBER(r.SYSTEM_RTC), NULL),
    IFF(REGEXP_LIKE(r.RFB, '[0-9]+'), TRY_TO_NUMBER(r.RFB), NULL),
    IFF(REGEXP_LIKE(r.TOTAL_RFB, '[0-9]+'), TRY_TO_NUMBER(r.TOTAL_RFB), NULL),
    r.COMPLIANCE_STATUS,
    r.COMPLIANCE_REASON,
    IFF(REGEXP_LIKE(r.RTO_CHANGE_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.RTO_CHANGE_DATE, 'YYYY-MM-DD'), NULL),
    r.GRN,
    r.APPLICATION_NAME,
    r.APPLICATION_RTO,
    r.HAS_CTIRICAL_KBS,
    r.LIFECYCLE_PHASE,
    r.ASSET_RISK_RATING_2,
    r.ARR_AVAILABILITY,
    r.ARR_CONFIDENTIALITY,
    r.ARR_INTEGRITY,
    r.IS_MERGERS_ACQUISITIONS_ASSET,
    r.ACQUIRED_ENTITY,
    r.BU_SUPER_DIVISION,
    r.BU_DIVISION,
    r.BU_SUPER_DEPARTMENT,
    r.BU_DEPARTMENT,
    r.ORG_GROUP_TYPE,
    r.SUPER_DIVISION,
    r.DIVISION,
    r.SUPER_DEPARTMENT,
    r.DEPARTMENT,
    r.BUS_ORG_LG_NM,
    r.COST_CENTER_CODE,
    r.COST_CENTER_NAME,
    r.EMPLOYEE_BUILDING_NAME,
    r.EMPLOYEE_COUNTRY_NAME,
    r.PRIMARY_BUS_FIRST_NAME,
    r.PRIMARY_BUS_LAST_NAME,
    r.PRIMARY_IT_FIRST_NAME,
    r.PRIMARY_IT_LAST_NAME,
    r.LEGAL_ENTITY_CODE,
    r.LEGAL_ENTITY_NAME,
    r.IS_USBANKS,
    r.IS_MSBNA,
    r.IS_MSPBNA,
    r.USBANKS_LE_LIST,
    r.KBS_FLAG_FLAG,
    IFF(REGEXP_LIKE(r.REPORTING_MONTHEND_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.REPORTING_MONTHEND_DATE, 'YYYY-MM-DD'), NULL),
    IFF(REGEXP_LIKE(r.REPORTING_MONTH, '[0-9]+'), TRY_TO_NUMBER(r.REPORTING_MONTH), NULL),
    IFF(REGEXP_LIKE(r.REPORTING_YEAR, '[0-9]+'), TRY_TO_NUMBER(r.REPORTING_YEAR), NULL),
    r.LOAD_BATCH_ID,
    r.SOURCE_FILE_ROW_NUMBER,
    ARRAY_CONSTRUCT_COMPACT(
        IFF(r.METRIC_DATE IS NOT NULL AND IFF(REGEXP_LIKE(r.METRIC_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.METRIC_DATE, 'YYYY-MM-DD'), NULL) IS NULL, 'METRIC_DATE', NULL),
        IFF(r.IS_NUMERATOR IS NOT NULL AND IFF(REGEXP_LIKE(r.IS_NUMERATOR, '[0-9]+'), TRY_TO_NUMBER(r.IS_NUMERATOR), NULL) IS NULL, 'IS_NUMERATOR', NULL),
        IFF(r.IS_DENOMINATOR IS NOT NULL AND IFF(REGEXP_LIKE(r.IS_DENOMINATOR, '[0-9]+'), TRY_TO_NUMBER(r.IS_DENOMINATOR), NULL) IS NULL, 'IS_DENOMINATOR', NULL),
        IFF(r.APPLICATION_TIER IS NOT NULL AND IFF(REGEXP_LIKE(r.APPLICATION_TIER, '[0-9]+'), TRY_TO_NUMBER(r.APPLICATION_TIER), NULL) IS NULL, 'APPLICATION_TIER', NULL),
        IFF(r.SYSTEM_RTC IS NOT NULL AND IFF(REGEXP_LIKE(r.SYSTEM_RTC, '[0-9]+'), TRY_TO_NUMBER(r.SYSTEM_RTC), NULL) IS NULL, 'SYSTEM_RTC', NULL),
        IFF(r.RFB IS NOT NULL AND IFF(REGEXP_LIKE(r.RFB, '[0-9]+'), TRY_TO_NUMBER(r.RFB), NULL) IS NULL, 'RFB', NULL),
        IFF(r.TOTAL_RFB IS NOT NULL AND IFF(REGEXP_LIKE(r.TOTAL_RFB, '[0-9]+'), TRY_TO_NUMBER(r.TOTAL_RFB), NULL) IS NULL, 'TOTAL_RFB', NULL),
        IFF(r.RTO_CHANGE_DATE IS NOT NULL AND IFF(REGEXP_LIKE(r.RTO_CHANGE_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.RTO_CHANGE_DATE, 'YYYY-MM-DD'), NULL) IS NULL, 'RTO_CHANGE_DATE', NULL),
        IFF(r.REPORTING_MONTHEND_DATE IS NOT NULL AND IFF(REGEXP_LIKE(r.REPORTING_MONTHEND_DATE, '[0-9]{4}-[0-9]{2}-[0-9]{2}'), TRY_TO_DATE(r.REPORTING_MONTHEND_DATE, 'YYYY-MM-DD'), NULL) IS NULL, 'REPORTING_MONTHEND_DATE', NULL),
        IFF(r.REPORTING_MONTH IS NOT NULL AND IFF(REGEXP_LIKE(r.REPORTING_MONTH, '[0-9]+'), TRY_TO_NUMBER(r.REPORTING_MONTH), NULL) IS NULL, 'REPORTING_MONTH', NULL),
        IFF(r.REPORTING_YEAR IS NOT NULL AND IFF(REGEXP_LIKE(r.REPORTING_YEAR, '[0-9]+'), TRY_TO_NUMBER(r.REPORTING_YEAR), NULL) IS NULL, 'REPORTING_YEAR', NULL)
    )
FROM RAW_APPLICATION_COMPLIANCE r
WHERE r.LOAD_BATCH_ID = 'MOCK_V1_20261103'
  AND NOT EXISTS (SELECT 1 FROM STG_APPLICATION_COMPLIANCE s WHERE s.LOAD_BATCH_ID = r.LOAD_BATCH_ID);
-- Expected: 11399 rows inserted. Running this again inserts 0 rows (guarded by batch id).

-- Checkpoint 06
SELECT COUNT(*)                                   AS stg_rows,                 -- Expected 11399
       COUNT_IF(ARRAY_SIZE(CONVERSION_ERRORS) > 0) AS rows_with_conversion_errors  -- Expected 0
FROM STG_APPLICATION_COMPLIANCE
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103';

UPDATE DATASET_LOAD_AUDIT
SET ROWS_STG = (SELECT COUNT(*) FROM STG_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
    STATUS = 'STAGED', UPDATED_AT = CURRENT_TIMESTAMP()
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND STATUS = 'RAW_LOADED'
  AND (SELECT COUNT(*) FROM STG_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103')
    = (SELECT COUNT(*) FROM RAW_APPLICATION_COMPLIANCE   WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103');
-- Expected: 1 row updated. 0 rows updated: staging count differs from raw count. STOP, capture the checkpoint output.
-- Conversion errors are not fatal here; script 07 decides whether the batch may be promoted.


-- ##################### 07_validate_staging.sql #####################
-- =====================================================================================
-- 07_validate_staging.sql
-- Validates the typed staging rows. Creates two views (no data is changed):
--   V_STG_ROW_VALIDATION      one row per staged row with REJECT_REASONS (blocking) and WARNINGS (non-blocking)
--   V_STG_VALIDATION_RESULTS  one row per check with observed vs expected and PASS/FAIL/INFO
-- The batch is marked VALIDATED only when every blocking set-level check passes and the number of rejected rows
-- is within the limit you set in 7.4. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 7.1 Row-level rules.  BLOCKING rules put the row in REJECT_REASONS. WARNING rules never reject a row.
CREATE OR REPLACE VIEW V_STG_ROW_VALIDATION AS
SELECT
    s.*,
    ARRAY_CONSTRUCT_COMPACT(
        IFF(ARRAY_SIZE(s.CONVERSION_ERRORS) > 0, 'CONVERSION_ERROR', NULL),
        IFF(s.METRIC_ID IS NULL, 'NULL_IN_REQUIRED_COLUMN:METRIC_ID', NULL),
        IFF(s.METRIC_DATE IS NULL, 'NULL_IN_REQUIRED_COLUMN:METRIC_DATE', NULL),
        IFF(s.METRIC_DATE_TYPE IS NULL, 'NULL_IN_REQUIRED_COLUMN:METRIC_DATE_TYPE', NULL),
        IFF(s.IS_NUMERATOR IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_NUMERATOR', NULL),
        IFF(s.IS_DENOMINATOR IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_DENOMINATOR', NULL),
        IFF(s.EON_ID IS NULL, 'NULL_IN_REQUIRED_COLUMN:EON_ID', NULL),
        IFF(s.BUILDING_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:BUILDING_NAME', NULL),
        IFF(s.EVENT_LOCATION IS NULL, 'NULL_IN_REQUIRED_COLUMN:EVENT_LOCATION', NULL),
        IFF(s.APPLICATION_TIER IS NULL, 'NULL_IN_REQUIRED_COLUMN:APPLICATION_TIER', NULL),
        IFF(s.TEST_STATUS IS NULL, 'NULL_IN_REQUIRED_COLUMN:TEST_STATUS', NULL),
        IFF(s.SYSTEM_RTC IS NULL, 'NULL_IN_REQUIRED_COLUMN:SYSTEM_RTC', NULL),
        IFF(s.COMPLIANCE_STATUS IS NULL, 'NULL_IN_REQUIRED_COLUMN:COMPLIANCE_STATUS', NULL),
        IFF(s.COMPLIANCE_REASON IS NULL, 'NULL_IN_REQUIRED_COLUMN:COMPLIANCE_REASON', NULL),
        IFF(s.GRN IS NULL, 'NULL_IN_REQUIRED_COLUMN:GRN', NULL),
        IFF(s.APPLICATION_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:APPLICATION_NAME', NULL),
        IFF(s.APPLICATION_RTO IS NULL, 'NULL_IN_REQUIRED_COLUMN:APPLICATION_RTO', NULL),
        IFF(s.HAS_CTIRICAL_KBS IS NULL, 'NULL_IN_REQUIRED_COLUMN:HAS_CTIRICAL_KBS', NULL),
        IFF(s.LIFECYCLE_PHASE IS NULL, 'NULL_IN_REQUIRED_COLUMN:LIFECYCLE_PHASE', NULL),
        IFF(s.ASSET_RISK_RATING_2 IS NULL, 'NULL_IN_REQUIRED_COLUMN:ASSET_RISK_RATING_2', NULL),
        IFF(s.ARR_AVAILABILITY IS NULL, 'NULL_IN_REQUIRED_COLUMN:ARR_AVAILABILITY', NULL),
        IFF(s.ARR_CONFIDENTIALITY IS NULL, 'NULL_IN_REQUIRED_COLUMN:ARR_CONFIDENTIALITY', NULL),
        IFF(s.ARR_INTEGRITY IS NULL, 'NULL_IN_REQUIRED_COLUMN:ARR_INTEGRITY', NULL),
        IFF(s.IS_MERGERS_ACQUISITIONS_ASSET IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_MERGERS_ACQUISITIONS_ASSET', NULL),
        IFF(s.ACQUIRED_ENTITY IS NULL, 'NULL_IN_REQUIRED_COLUMN:ACQUIRED_ENTITY', NULL),
        IFF(s.BU_SUPER_DIVISION IS NULL, 'NULL_IN_REQUIRED_COLUMN:BU_SUPER_DIVISION', NULL),
        IFF(s.BU_DIVISION IS NULL, 'NULL_IN_REQUIRED_COLUMN:BU_DIVISION', NULL),
        IFF(s.BU_SUPER_DEPARTMENT IS NULL, 'NULL_IN_REQUIRED_COLUMN:BU_SUPER_DEPARTMENT', NULL),
        IFF(s.ORG_GROUP_TYPE IS NULL, 'NULL_IN_REQUIRED_COLUMN:ORG_GROUP_TYPE', NULL),
        IFF(s.SUPER_DIVISION IS NULL, 'NULL_IN_REQUIRED_COLUMN:SUPER_DIVISION', NULL),
        IFF(s.DIVISION IS NULL, 'NULL_IN_REQUIRED_COLUMN:DIVISION', NULL),
        IFF(s.SUPER_DEPARTMENT IS NULL, 'NULL_IN_REQUIRED_COLUMN:SUPER_DEPARTMENT', NULL),
        IFF(s.BUS_ORG_LG_NM IS NULL, 'NULL_IN_REQUIRED_COLUMN:BUS_ORG_LG_NM', NULL),
        IFF(s.COST_CENTER_CODE IS NULL, 'NULL_IN_REQUIRED_COLUMN:COST_CENTER_CODE', NULL),
        IFF(s.COST_CENTER_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:COST_CENTER_NAME', NULL),
        IFF(s.EMPLOYEE_BUILDING_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:EMPLOYEE_BUILDING_NAME', NULL),
        IFF(s.EMPLOYEE_COUNTRY_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:EMPLOYEE_COUNTRY_NAME', NULL),
        IFF(s.PRIMARY_BUS_FIRST_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:PRIMARY_BUS_FIRST_NAME', NULL),
        IFF(s.PRIMARY_BUS_LAST_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:PRIMARY_BUS_LAST_NAME', NULL),
        IFF(s.PRIMARY_IT_FIRST_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:PRIMARY_IT_FIRST_NAME', NULL),
        IFF(s.PRIMARY_IT_LAST_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:PRIMARY_IT_LAST_NAME', NULL),
        IFF(s.LEGAL_ENTITY_CODE IS NULL, 'NULL_IN_REQUIRED_COLUMN:LEGAL_ENTITY_CODE', NULL),
        IFF(s.LEGAL_ENTITY_NAME IS NULL, 'NULL_IN_REQUIRED_COLUMN:LEGAL_ENTITY_NAME', NULL),
        IFF(s.IS_USBANKS IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_USBANKS', NULL),
        IFF(s.IS_MSBNA IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_MSBNA', NULL),
        IFF(s.IS_MSPBNA IS NULL, 'NULL_IN_REQUIRED_COLUMN:IS_MSPBNA', NULL),
        IFF(s.KBS_FLAG_FLAG IS NULL, 'NULL_IN_REQUIRED_COLUMN:KBS_FLAG_FLAG', NULL),
        IFF(s.REPORTING_MONTHEND_DATE IS NULL, 'NULL_IN_REQUIRED_COLUMN:REPORTING_MONTHEND_DATE', NULL),
        IFF(s.REPORTING_MONTH IS NULL, 'NULL_IN_REQUIRED_COLUMN:REPORTING_MONTH', NULL),
        IFF(s.REPORTING_YEAR IS NULL, 'NULL_IN_REQUIRED_COLUMN:REPORTING_YEAR', NULL),
        IFF(s.METRIC_DATE <> s.REPORTING_MONTHEND_DATE, 'METRIC_DATE_NE_REPORTING_MONTHEND_DATE', NULL),
        IFF(s.REPORTING_MONTHEND_DATE <> LAST_DAY(s.REPORTING_MONTHEND_DATE), 'REPORTING_DATE_NOT_MONTH_END', NULL),
        IFF(s.REPORTING_MONTH <> MONTH(s.REPORTING_MONTHEND_DATE) OR s.REPORTING_YEAR <> YEAR(s.REPORTING_MONTHEND_DATE), 'MONTH_YEAR_DISAGREE_WITH_DATE', NULL),
        IFF(s.IS_NUMERATOR NOT IN (0,1) OR s.IS_DENOMINATOR NOT IN (0,1) OR s.SYSTEM_RTC NOT IN (0,1), 'FLAG_NOT_0_OR_1', NULL),
        IFF(s.IS_NUMERATOR = 1 AND s.IS_DENOMINATOR = 0, 'NUMERATOR_WITHOUT_DENOMINATOR', NULL),
        IFF(s.APPLICATION_TIER NOT BETWEEN 1 AND 4, 'TIER_OUT_OF_RANGE', NULL),
        IFF(s.RFB < 0 OR s.RFB > 10000 OR s.TOTAL_RFB < 0 OR s.TOTAL_RFB > 10000, 'FINDINGS_OUT_OF_RANGE', NULL),
        IFF(s.RFB > s.TOTAL_RFB, 'RFB_GT_TOTAL_RFB', NULL),
        IFF(s.HAS_CTIRICAL_KBS NOT IN ('Y','N') OR s.IS_MERGERS_ACQUISITIONS_ASSET NOT IN ('Y','N') OR s.IS_USBANKS NOT IN ('Y','N')
            OR s.IS_MSBNA NOT IN ('Y','N') OR s.IS_MSPBNA NOT IN ('Y','N') OR s.KBS_FLAG_FLAG NOT IN ('Y','N'), 'YN_FLAG_DOMAIN', NULL),
        IFF(NOT REGEXP_LIKE(s.ASSET_RISK_RATING_2, 'P[1-4]'), 'RISK_CODE_DOMAIN', NULL),
        IFF(NOT REGEXP_LIKE(s.ARR_AVAILABILITY, 'A[1-4]') OR NOT REGEXP_LIKE(s.ARR_CONFIDENTIALITY, 'C[1-4]') OR NOT REGEXP_LIKE(s.ARR_INTEGRITY, 'I[1-4]'), 'ARR_CODE_DOMAIN', NULL),
        IFF(s.TEST_STATUS NOT IN ('Test_Complete','No_Test','Test_Pending','Exempt'), 'TEST_STATUS_DOMAIN', NULL),
        IFF(s.TEST_RESULT IS NOT NULL AND s.TEST_RESULT NOT IN ('Pass','Fail'), 'TEST_RESULT_DOMAIN', NULL),
        IFF(s.TEST_RESULT IS NOT NULL AND s.TEST_STATUS <> 'Test_Complete', 'TEST_RESULT_WITHOUT_COMPLETE_TEST', NULL),
        IFF(s.COMPLIANCE_STATUS NOT IN ('Compliant','Non_Compliant','Pending','Not_Applicable'), 'COMPLIANCE_STATUS_DOMAIN', NULL),
        IFF(s.RTO_CHANGE_DATE > s.METRIC_DATE, 'RTO_CHANGE_AFTER_METRIC_DATE', NULL),
        IFF(s.ORG_GROUP_TYPE NOT IN ('DEPARTMENT','SUPER_DEPARTMENT'), 'ORG_GROUP_TYPE_DOMAIN', NULL),
        IFF((s.ORG_GROUP_TYPE = 'DEPARTMENT'       AND (s.DEPARTMENT IS NULL OR s.BU_DEPARTMENT IS NULL))
         OR (s.ORG_GROUP_TYPE = 'SUPER_DEPARTMENT' AND (s.DEPARTMENT IS NOT NULL OR s.BU_DEPARTMENT IS NOT NULL)), 'ORG_LEVEL_VS_DEPARTMENT_NULLS', NULL),
        IFF((s.IS_MERGERS_ACQUISITIONS_ASSET = 'Y' AND s.ACQUIRED_ENTITY = 'NON_ACQUIRED_ENTITY')
         OR (s.IS_MERGERS_ACQUISITIONS_ASSET = 'N' AND s.ACQUIRED_ENTITY <> 'NON_ACQUIRED_ENTITY'), 'MA_FLAG_VS_ACQUIRED_ENTITY', NULL),
        IFF(s.USBANKS_LE_LIST IS DISTINCT FROM NULLIF(CONCAT_WS('|', IFF(s.IS_USBANKS = 'Y', 'BANK_A', NULL), IFF(s.IS_MSBNA = 'Y', 'BANK_B', NULL), IFF(s.IS_MSPBNA = 'Y', 'BANK_C', NULL)), ''),
            'BANK_LIST_VS_FLAGS', NULL)
    ) AS REJECT_REASONS,
    ARRAY_CONSTRUCT_COMPACT(
        IFF(s.TEST_STATUS = 'Test_Complete' AND s.TEST_RESULT IS NULL, 'W_TEST_COMPLETE_WITHOUT_RESULT', NULL),
        IFF(s.TEST_STATUS = 'Exempt' AND s.EXEMPTION_LEVEL_1 IS NULL, 'W_EXEMPT_WITHOUT_EXEMPTION_LEVEL', NULL),
        IFF(s.RFB IS NULL, 'W_RFB_NULL', NULL),
        IFF(s.TOTAL_RFB IS NULL, 'W_TOTAL_RFB_NULL', NULL),
        IFF(s.HAS_CTIRICAL_KBS <> s.KBS_FLAG_FLAG, 'W_KBS_FLAGS_DISAGREE', NULL),
        IFF(s.COMPLIANCE_STATUS = 'Compliant' AND s.TEST_STATUS NOT IN ('Test_Complete','Exempt'), 'W_COMPLIANT_WITHOUT_COMPLETE_OR_EXEMPT_TEST', NULL),
        IFF(s.COMPLIANCE_STATUS = 'Not_Applicable' AND s.TEST_STATUS IN ('Test_Complete','Test_Pending'), 'W_NOT_APPLICABLE_WITH_ACTIVE_TEST', NULL),
        IFF(s.COMPLIANCE_STATUS = 'Pending' AND s.TEST_STATUS = 'Exempt', 'W_PENDING_BUT_EXEMPT', NULL),
        IFF((s.COMPLIANCE_STATUS = 'Compliant' AND NOT (s.IS_NUMERATOR = 1 AND s.IS_DENOMINATOR = 1))
         OR (s.COMPLIANCE_STATUS = 'Non_Compliant' AND NOT (s.IS_NUMERATOR = 0 AND s.IS_DENOMINATOR = 1))
         OR (s.COMPLIANCE_STATUS = 'Not_Applicable' AND NOT (s.IS_NUMERATOR = 0 AND s.IS_DENOMINATOR = 0)), 'W_FLAGS_VS_STATUS_PROVISIONAL_RULE', NULL)
    ) AS WARNINGS
FROM STG_APPLICATION_COMPLIANCE s;

-- 7.2 Check results (set-level relationship checks + row-rule totals + warnings).
--     SEVERITY BLOCKING: OBSERVED must equal EXPECTED. INFO: documented known behaviour of this dataset, never blocks.
CREATE OR REPLACE VIEW V_STG_VALIDATION_RESULTS AS
WITH b AS (SELECT * FROM STG_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
v AS (SELECT * FROM V_STG_ROW_VALIDATION WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
checks AS (
    SELECT 'ROW_COUNT'                       AS CHECK_NAME, 'BLOCKING' AS SEVERITY, (SELECT COUNT(*) FROM b) AS OBSERVED, 11399 AS EXPECTED
    UNION ALL SELECT 'CONVERSION_ERROR_ROWS', 'BLOCKING', (SELECT COUNT_IF(ARRAY_SIZE(CONVERSION_ERRORS) > 0) FROM b), 0
    UNION ALL SELECT 'ROW_RULE_REJECTED_ROWS', 'BLOCKING', (SELECT COUNT_IF(ARRAY_SIZE(REJECT_REASONS) > 0) FROM v), 0
    UNION ALL SELECT 'DUPLICATE_CANDIDATE_KEY_GROUPS (EON_ID, METRIC_ID, METRIC_DATE)', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT 1 FROM b GROUP BY EON_ID, METRIC_ID, METRIC_DATE HAVING COUNT(*) > 1)), 0
    UNION ALL SELECT 'EON_ID_NOT_1_TO_1_WITH_GRN_AND_NAME', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT EON_ID FROM b GROUP BY EON_ID HAVING COUNT(DISTINCT GRN) > 1 OR COUNT(DISTINCT APPLICATION_NAME) > 1))
      + (SELECT COUNT(*) FROM (SELECT GRN FROM b GROUP BY GRN HAVING COUNT(DISTINCT EON_ID) > 1)), 0
    UNION ALL SELECT 'COST_CENTER_CODE_NAME_NOT_1_TO_1', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT COST_CENTER_CODE FROM b GROUP BY 1 HAVING COUNT(DISTINCT COST_CENTER_NAME) > 1))
      + (SELECT COUNT(*) FROM (SELECT COST_CENTER_NAME FROM b GROUP BY 1 HAVING COUNT(DISTINCT COST_CENTER_CODE) > 1)), 0
    UNION ALL SELECT 'LEGAL_ENTITY_CODE_NAME_NOT_1_TO_1', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT LEGAL_ENTITY_CODE FROM b GROUP BY 1 HAVING COUNT(DISTINCT LEGAL_ENTITY_NAME) > 1))
      + (SELECT COUNT(*) FROM (SELECT LEGAL_ENTITY_NAME FROM b GROUP BY 1 HAVING COUNT(DISTINCT LEGAL_ENTITY_CODE) > 1)), 0
    UNION ALL SELECT 'LEGAL_ENTITY_BANK_FLAGS_NOT_CONSTANT', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT LEGAL_ENTITY_CODE FROM b GROUP BY 1
            HAVING COUNT(DISTINCT IS_USBANKS) > 1 OR COUNT(DISTINCT IS_MSBNA) > 1 OR COUNT(DISTINCT IS_MSPBNA) > 1 OR COUNT(DISTINCT USBANKS_LE_LIST) > 1)), 0
    UNION ALL SELECT 'HIERARCHY_2_PARENT_CHILD', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT DIVISION FROM b GROUP BY 1 HAVING COUNT(DISTINCT SUPER_DIVISION) > 1))
      + (SELECT COUNT(*) FROM (SELECT SUPER_DEPARTMENT FROM b GROUP BY 1 HAVING COUNT(DISTINCT DIVISION) > 1))
      + (SELECT COUNT(*) FROM (SELECT DEPARTMENT FROM b WHERE DEPARTMENT IS NOT NULL GROUP BY 1 HAVING COUNT(DISTINCT SUPER_DEPARTMENT) > 1)), 0
    UNION ALL SELECT 'HIERARCHY_1_BU_PARENT_CHILD', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT BU_DIVISION FROM b GROUP BY 1 HAVING COUNT(DISTINCT BU_SUPER_DIVISION) > 1))
      + (SELECT COUNT(*) FROM (SELECT BU_SUPER_DEPARTMENT FROM b GROUP BY 1 HAVING COUNT(DISTINCT BU_DIVISION) > 1))
      + (SELECT COUNT(*) FROM (SELECT BU_DEPARTMENT FROM b WHERE BU_DEPARTMENT IS NOT NULL GROUP BY 1 HAVING COUNT(DISTINCT BU_SUPER_DEPARTMENT) > 1)), 0
    UNION ALL SELECT 'BUILDING_TO_LOCATION_AND_COUNTRY_MAPPING', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT BUILDING_NAME FROM b GROUP BY 1 HAVING COUNT(DISTINCT EVENT_LOCATION) > 1))
      + (SELECT COUNT(*) FROM (SELECT EMPLOYEE_BUILDING_NAME FROM b GROUP BY 1 HAVING COUNT(DISTINCT EMPLOYEE_COUNTRY_NAME) > 1)), 0
    UNION ALL SELECT 'APPLICATION_ATTRIBUTES_VARY_WITHIN_APP_MONTH', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT EON_ID, REPORTING_MONTHEND_DATE FROM b GROUP BY 1, 2
            HAVING COUNT(DISTINCT BUILDING_NAME) > 1
        OR COUNT(DISTINCT EVENT_LOCATION) > 1
        OR COUNT(DISTINCT APPLICATION_TIER) > 1
        OR COUNT(DISTINCT RTO_CHANGE_DATE) > 1
        OR COUNT(DISTINCT GRN) > 1
        OR COUNT(DISTINCT APPLICATION_NAME) > 1
        OR COUNT(DISTINCT APPLICATION_RTO) > 1
        OR COUNT(DISTINCT HAS_CTIRICAL_KBS) > 1
        OR COUNT(DISTINCT LIFECYCLE_PHASE) > 1
        OR COUNT(DISTINCT ASSET_RISK_RATING_2) > 1
        OR COUNT(DISTINCT ARR_AVAILABILITY) > 1
        OR COUNT(DISTINCT ARR_CONFIDENTIALITY) > 1
        OR COUNT(DISTINCT ARR_INTEGRITY) > 1
        OR COUNT(DISTINCT IS_MERGERS_ACQUISITIONS_ASSET) > 1
        OR COUNT(DISTINCT ACQUIRED_ENTITY) > 1
        OR COUNT(DISTINCT BU_SUPER_DIVISION) > 1
        OR COUNT(DISTINCT BU_DIVISION) > 1
        OR COUNT(DISTINCT BU_SUPER_DEPARTMENT) > 1
        OR COUNT(DISTINCT BU_DEPARTMENT) > 1
        OR COUNT(DISTINCT ORG_GROUP_TYPE) > 1
        OR COUNT(DISTINCT SUPER_DIVISION) > 1
        OR COUNT(DISTINCT DIVISION) > 1
        OR COUNT(DISTINCT SUPER_DEPARTMENT) > 1
        OR COUNT(DISTINCT DEPARTMENT) > 1
        OR COUNT(DISTINCT BUS_ORG_LG_NM) > 1
        OR COUNT(DISTINCT COST_CENTER_CODE) > 1
        OR COUNT(DISTINCT COST_CENTER_NAME) > 1
        OR COUNT(DISTINCT EMPLOYEE_BUILDING_NAME) > 1
        OR COUNT(DISTINCT EMPLOYEE_COUNTRY_NAME) > 1
        OR COUNT(DISTINCT PRIMARY_BUS_FIRST_NAME) > 1
        OR COUNT(DISTINCT PRIMARY_BUS_LAST_NAME) > 1
        OR COUNT(DISTINCT PRIMARY_IT_FIRST_NAME) > 1
        OR COUNT(DISTINCT PRIMARY_IT_LAST_NAME) > 1
        OR COUNT(DISTINCT LEGAL_ENTITY_CODE) > 1
        OR COUNT(DISTINCT LEGAL_ENTITY_NAME) > 1
        OR COUNT(DISTINCT IS_USBANKS) > 1
        OR COUNT(DISTINCT IS_MSBNA) > 1
        OR COUNT(DISTINCT IS_MSPBNA) > 1
        OR COUNT(DISTINCT USBANKS_LE_LIST) > 1
        OR COUNT(DISTINCT KBS_FLAG_FLAG) > 1
        OR COUNT(DISTINCT REPORTING_MONTH) > 1
        OR COUNT(DISTINCT REPORTING_YEAR) > 1)), 0
    UNION ALL SELECT 'TOTAL_RFB_VARIES_WITHIN_APP_MONTH', 'BLOCKING',
        (SELECT COUNT(*) FROM (SELECT EON_ID, REPORTING_MONTHEND_DATE FROM b GROUP BY 1, 2 HAVING COUNT(DISTINCT TOTAL_RFB) > 1)), 0
    -- Known, documented behaviour of this synthetic dataset (INFO, never blocks):
    UNION ALL SELECT 'INFO TEST_COMPLETE_WITHOUT_RESULT',           'INFO', (SELECT COUNT_IF(ARRAY_CONTAINS('W_TEST_COMPLETE_WITHOUT_RESULT'::VARIANT, WARNINGS)) FROM v), 63
    UNION ALL SELECT 'INFO EXEMPT_WITHOUT_EXEMPTION_LEVEL',         'INFO', (SELECT COUNT_IF(ARRAY_CONTAINS('W_EXEMPT_WITHOUT_EXEMPTION_LEVEL'::VARIANT, WARNINGS)) FROM v), 30
    UNION ALL SELECT 'INFO RFB_NULL',                               'INFO', (SELECT COUNT_IF(ARRAY_CONTAINS('W_RFB_NULL'::VARIANT, WARNINGS)) FROM v), 123
    UNION ALL SELECT 'INFO TOTAL_RFB_NULL',                         'INFO', (SELECT COUNT_IF(ARRAY_CONTAINS('W_TOTAL_RFB_NULL'::VARIANT, WARNINGS)) FROM v), 117
    UNION ALL SELECT 'INFO OTHER_WARNING_ROWS (kbs / status-vs-test / flags-vs-status)', 'INFO',
        (SELECT COUNT_IF(ARRAY_SIZE(ARRAY_EXCEPT(WARNINGS, ARRAY_CONSTRUCT('W_TEST_COMPLETE_WITHOUT_RESULT','W_EXEMPT_WITHOUT_EXEMPTION_LEVEL','W_RFB_NULL','W_TOTAL_RFB_NULL'))) > 0) FROM v), 0
)
SELECT CHECK_NAME, SEVERITY, OBSERVED, EXPECTED,
       CASE WHEN OBSERVED = EXPECTED THEN 'PASS'
            WHEN SEVERITY = 'BLOCKING' THEN 'FAIL'
            ELSE 'REVIEW' END AS STATUS
FROM checks;

-- 7.3 Read the results.
SELECT * FROM V_STG_VALIDATION_RESULTS ORDER BY SEVERITY, CHECK_NAME;
-- Expected: every BLOCKING row PASS. INFO rows PASS with the observed values shown in the EXPECTED column
-- (these are known properties of the generated data, listed in DATA_MODEL.md). An INFO row showing REVIEW means
-- the data differs from what was documented: read it, do not ignore it.
-- If any BLOCKING row is FAIL: STOP. Capture this result set plus the rows below.

-- 7.3b Why were rows rejected? (empty when nothing failed)
SELECT SOURCE_FILE_ROW_NUMBER, EON_ID, METRIC_ID, REJECT_REASONS
FROM V_STG_ROW_VALIDATION
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND ARRAY_SIZE(REJECT_REASONS) > 0
ORDER BY SOURCE_FILE_ROW_NUMBER
LIMIT 200;

-- 7.4 Quarantine policy. For this dataset the expected number of rejected rows is 0.
--     The policy is: if ANY row is rejected, stop and investigate; quarantining a known number is acceptable ONLY if you
--     raise MAX_REJECTS_ALLOWED below on purpose AND write the reason in NOTES. Unexplained rejects are never acceptable.
SET MAX_REJECTS_ALLOWED = 0;

UPDATE DATASET_LOAD_AUDIT
SET STATUS = 'VALIDATED',
    ROWS_REJECTED = (SELECT COUNT_IF(ARRAY_SIZE(REJECT_REASONS) > 0) FROM V_STG_ROW_VALIDATION WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
    UPDATED_AT = CURRENT_TIMESTAMP()
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND STATUS = 'STAGED'
  AND (SELECT COUNT(*) FROM V_STG_VALIDATION_RESULTS WHERE SEVERITY = 'BLOCKING' AND STATUS = 'FAIL'
         AND CHECK_NAME <> 'ROW_RULE_REJECTED_ROWS' AND CHECK_NAME <> 'CONVERSION_ERROR_ROWS') = 0
  AND (SELECT COUNT_IF(ARRAY_SIZE(REJECT_REASONS) > 0) FROM V_STG_ROW_VALIDATION WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') <= $MAX_REJECTS_ALLOWED;
-- Expected: 1 row updated and STATUS = VALIDATED. 0 rows updated: a blocking check failed or rejects exceed the limit.
-- Note: conversion-failed rows also carry CONVERSION_ERROR in REJECT_REASONS, so they are counted by the reject limit.

SELECT LOAD_BATCH_ID, STATUS, ROWS_RAW, ROWS_STG, ROWS_REJECTED FROM DATASET_LOAD_AUDIT WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103';
-- Checkpoint 07: STATUS = VALIDATED, ROWS_RAW = ROWS_STG = 11399, ROWS_REJECTED = 0.


-- ##################### 08_create_final_tables.sql #####################
-- =====================================================================================
-- 08_create_final_tables.sql
-- The analytical table. Typed, NOT NULL where the data dictionary says the column is never blank.
-- CREATE TABLE IF NOT EXISTS: re-running never drops or empties data. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- Grain (verified on the generated file, enforced as a blocking check in script 07 and again in script 10):
--   one row per EON_ID x METRIC_ID x METRIC_DATE   (11,399 rows; 0 duplicate keys).
-- The client specification explicitly allows EON_ID and METRIC_ID to repeat, and a future real extract may repeat the
-- full key. Snowflake does not enforce PRIMARY KEY/UNIQUE on standard tables, so uniqueness is checked, not declared.
CREATE TABLE IF NOT EXISTS APPLICATION_COMPLIANCE (
    METRIC_ID VARCHAR(20) NOT NULL,
    METRIC_DATE DATE NOT NULL,
    METRIC_DATE_TYPE VARCHAR(20) NOT NULL,
    IS_NUMERATOR NUMBER(1,0) NOT NULL,
    IS_DENOMINATOR NUMBER(1,0) NOT NULL,
    EON_ID VARCHAR(20) NOT NULL,
    BUILDING_NAME VARCHAR(50) NOT NULL,
    EVENT_LOCATION VARCHAR(50) NOT NULL,
    APPLICATION_TIER NUMBER(1,0) NOT NULL,
    EXEMPTION_LEVEL_1 VARCHAR(50),
    TEST_STATUS VARCHAR(30) NOT NULL,
    TEST_RESULT VARCHAR(20),
    SYSTEM_RTC NUMBER(1,0) NOT NULL,
    RFB NUMBER(10,0),
    TOTAL_RFB NUMBER(10,0),
    COMPLIANCE_STATUS VARCHAR(30) NOT NULL,
    COMPLIANCE_REASON VARCHAR(60) NOT NULL,
    RTO_CHANGE_DATE DATE,
    GRN VARCHAR(100) NOT NULL,
    APPLICATION_NAME VARCHAR(100) NOT NULL,
    APPLICATION_RTO VARCHAR(30) NOT NULL,
    HAS_CTIRICAL_KBS VARCHAR(1) NOT NULL,
    LIFECYCLE_PHASE VARCHAR(30) NOT NULL,
    ASSET_RISK_RATING_2 VARCHAR(10) NOT NULL,
    ARR_AVAILABILITY VARCHAR(10) NOT NULL,
    ARR_CONFIDENTIALITY VARCHAR(10) NOT NULL,
    ARR_INTEGRITY VARCHAR(10) NOT NULL,
    IS_MERGERS_ACQUISITIONS_ASSET VARCHAR(1) NOT NULL,
    ACQUIRED_ENTITY VARCHAR(60) NOT NULL,
    BU_SUPER_DIVISION VARCHAR(100) NOT NULL,
    BU_DIVISION VARCHAR(100) NOT NULL,
    BU_SUPER_DEPARTMENT VARCHAR(100) NOT NULL,
    BU_DEPARTMENT VARCHAR(100),
    ORG_GROUP_TYPE VARCHAR(30) NOT NULL,
    SUPER_DIVISION VARCHAR(100) NOT NULL,
    DIVISION VARCHAR(100) NOT NULL,
    SUPER_DEPARTMENT VARCHAR(100) NOT NULL,
    DEPARTMENT VARCHAR(100),
    BUS_ORG_LG_NM VARCHAR(100) NOT NULL,
    COST_CENTER_CODE VARCHAR(20) NOT NULL,
    COST_CENTER_NAME VARCHAR(100) NOT NULL,
    EMPLOYEE_BUILDING_NAME VARCHAR(50) NOT NULL,
    EMPLOYEE_COUNTRY_NAME VARCHAR(50) NOT NULL,
    PRIMARY_BUS_FIRST_NAME VARCHAR(100) NOT NULL,
    PRIMARY_BUS_LAST_NAME VARCHAR(100) NOT NULL,
    PRIMARY_IT_FIRST_NAME VARCHAR(100) NOT NULL,
    PRIMARY_IT_LAST_NAME VARCHAR(100) NOT NULL,
    LEGAL_ENTITY_CODE VARCHAR(20) NOT NULL,
    LEGAL_ENTITY_NAME VARCHAR(100) NOT NULL,
    IS_USBANKS VARCHAR(1) NOT NULL,
    IS_MSBNA VARCHAR(1) NOT NULL,
    IS_MSPBNA VARCHAR(1) NOT NULL,
    USBANKS_LE_LIST VARCHAR(50),
    KBS_FLAG_FLAG VARCHAR(1) NOT NULL,
    REPORTING_MONTHEND_DATE DATE NOT NULL,
    REPORTING_MONTH NUMBER(2,0) NOT NULL,
    REPORTING_YEAR NUMBER(4,0) NOT NULL,
    -- derived / traceability columns (not source columns)
    OBSERVATION_KEY         VARCHAR      NOT NULL,   -- EON_ID|METRIC_ID|YYYY-MM-DD, the observed row grain
    LOAD_BATCH_ID           VARCHAR      NOT NULL,
    SOURCE_FILE_ROW_NUMBER  NUMBER(10,0) NOT NULL,
    PROMOTED_AT             TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Validated application compliance observations. Grain: EON_ID x METRIC_ID x METRIC_DATE (observed unique). 57 source columns + 4 derived/traceability columns.';

-- Clustering is unnecessary at 11k rows; none is declared.

-- Checkpoint 08
SELECT COUNT(*) AS final_columns
FROM METRICS_ANALYZER.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'MOCK_DATA' AND TABLE_NAME = 'APPLICATION_COMPLIANCE';
-- Expected: 61 (57 source + 4 derived)
SELECT COUNT(*) AS final_rows FROM APPLICATION_COMPLIANCE;
-- Expected: 0 on first run (script 09 fills it).


-- ##################### 09_promote_validated_data.sql #####################
-- =====================================================================================
-- 09_promote_validated_data.sql
-- Promotes ONLY validated rows. Rejected rows are quarantined with reasons. Both inserts are guarded:
-- nothing moves unless the audit record says VALIDATED, and nothing moves twice. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 9.1 Gate. Must return STATUS = VALIDATED. If not, STOP: script 07 did not pass.
SELECT LOAD_BATCH_ID, STATUS, ROWS_STG, ROWS_REJECTED
FROM DATASET_LOAD_AUDIT WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103';

-- 9.2 Quarantine rejected rows (expected 0 rows for this dataset).
INSERT INTO DATASET_REJECTED_ROWS (LOAD_BATCH_ID, SOURCE_FILE_ROW_NUMBER, EON_ID, METRIC_ID, METRIC_DATE_RAW, REJECT_REASONS, RAW_RECORD)
SELECT v.LOAD_BATCH_ID, v.SOURCE_FILE_ROW_NUMBER, r.EON_ID, r.METRIC_ID, r.METRIC_DATE, v.REJECT_REASONS, r.RAW_RECORD
FROM V_STG_ROW_VALIDATION v
JOIN (SELECT LOAD_BATCH_ID, SOURCE_FILE_ROW_NUMBER, EON_ID, METRIC_ID, METRIC_DATE,
             OBJECT_CONSTRUCT(*) AS RAW_RECORD   -- the whole raw row as an object (blank fields are omitted)
      FROM RAW_APPLICATION_COMPLIANCE) r
  ON r.LOAD_BATCH_ID = v.LOAD_BATCH_ID AND r.SOURCE_FILE_ROW_NUMBER = v.SOURCE_FILE_ROW_NUMBER
WHERE v.LOAD_BATCH_ID = 'MOCK_V1_20261103'
  AND ARRAY_SIZE(v.REJECT_REASONS) > 0
  AND EXISTS (SELECT 1 FROM DATASET_LOAD_AUDIT a WHERE a.LOAD_BATCH_ID = 'MOCK_V1_20261103' AND a.STATUS = 'VALIDATED')
  AND NOT EXISTS (SELECT 1 FROM DATASET_REJECTED_ROWS q WHERE q.LOAD_BATCH_ID = 'MOCK_V1_20261103');

-- 9.3 Promote validated rows with an explicit column list (no SELECT *).
INSERT INTO APPLICATION_COMPLIANCE (
    METRIC_ID, METRIC_DATE, METRIC_DATE_TYPE, IS_NUMERATOR,
    IS_DENOMINATOR, EON_ID, BUILDING_NAME, EVENT_LOCATION,
    APPLICATION_TIER, EXEMPTION_LEVEL_1, TEST_STATUS, TEST_RESULT,
    SYSTEM_RTC, RFB, TOTAL_RFB, COMPLIANCE_STATUS,
    COMPLIANCE_REASON, RTO_CHANGE_DATE, GRN, APPLICATION_NAME,
    APPLICATION_RTO, HAS_CTIRICAL_KBS, LIFECYCLE_PHASE, ASSET_RISK_RATING_2,
    ARR_AVAILABILITY, ARR_CONFIDENTIALITY, ARR_INTEGRITY, IS_MERGERS_ACQUISITIONS_ASSET,
    ACQUIRED_ENTITY, BU_SUPER_DIVISION, BU_DIVISION, BU_SUPER_DEPARTMENT,
    BU_DEPARTMENT, ORG_GROUP_TYPE, SUPER_DIVISION, DIVISION,
    SUPER_DEPARTMENT, DEPARTMENT, BUS_ORG_LG_NM, COST_CENTER_CODE,
    COST_CENTER_NAME, EMPLOYEE_BUILDING_NAME, EMPLOYEE_COUNTRY_NAME, PRIMARY_BUS_FIRST_NAME,
    PRIMARY_BUS_LAST_NAME, PRIMARY_IT_FIRST_NAME, PRIMARY_IT_LAST_NAME, LEGAL_ENTITY_CODE,
    LEGAL_ENTITY_NAME, IS_USBANKS, IS_MSBNA, IS_MSPBNA,
    USBANKS_LE_LIST, KBS_FLAG_FLAG, REPORTING_MONTHEND_DATE, REPORTING_MONTH,
    REPORTING_YEAR,
    OBSERVATION_KEY, LOAD_BATCH_ID, SOURCE_FILE_ROW_NUMBER
)
SELECT
    s.METRIC_ID, s.METRIC_DATE, s.METRIC_DATE_TYPE, s.IS_NUMERATOR,
    s.IS_DENOMINATOR, s.EON_ID, s.BUILDING_NAME, s.EVENT_LOCATION,
    s.APPLICATION_TIER, s.EXEMPTION_LEVEL_1, s.TEST_STATUS, s.TEST_RESULT,
    s.SYSTEM_RTC, s.RFB, s.TOTAL_RFB, s.COMPLIANCE_STATUS,
    s.COMPLIANCE_REASON, s.RTO_CHANGE_DATE, s.GRN, s.APPLICATION_NAME,
    s.APPLICATION_RTO, s.HAS_CTIRICAL_KBS, s.LIFECYCLE_PHASE, s.ASSET_RISK_RATING_2,
    s.ARR_AVAILABILITY, s.ARR_CONFIDENTIALITY, s.ARR_INTEGRITY, s.IS_MERGERS_ACQUISITIONS_ASSET,
    s.ACQUIRED_ENTITY, s.BU_SUPER_DIVISION, s.BU_DIVISION, s.BU_SUPER_DEPARTMENT,
    s.BU_DEPARTMENT, s.ORG_GROUP_TYPE, s.SUPER_DIVISION, s.DIVISION,
    s.SUPER_DEPARTMENT, s.DEPARTMENT, s.BUS_ORG_LG_NM, s.COST_CENTER_CODE,
    s.COST_CENTER_NAME, s.EMPLOYEE_BUILDING_NAME, s.EMPLOYEE_COUNTRY_NAME, s.PRIMARY_BUS_FIRST_NAME,
    s.PRIMARY_BUS_LAST_NAME, s.PRIMARY_IT_FIRST_NAME, s.PRIMARY_IT_LAST_NAME, s.LEGAL_ENTITY_CODE,
    s.LEGAL_ENTITY_NAME, s.IS_USBANKS, s.IS_MSBNA, s.IS_MSPBNA,
    s.USBANKS_LE_LIST, s.KBS_FLAG_FLAG, s.REPORTING_MONTHEND_DATE, s.REPORTING_MONTH,
    s.REPORTING_YEAR,
    s.EON_ID || '|' || s.METRIC_ID || '|' || TO_CHAR(s.METRIC_DATE, 'YYYY-MM-DD'),
    s.LOAD_BATCH_ID,
    s.SOURCE_FILE_ROW_NUMBER
FROM V_STG_ROW_VALIDATION s
WHERE s.LOAD_BATCH_ID = 'MOCK_V1_20261103'
  AND ARRAY_SIZE(s.REJECT_REASONS) = 0
  AND EXISTS (SELECT 1 FROM DATASET_LOAD_AUDIT a WHERE a.LOAD_BATCH_ID = 'MOCK_V1_20261103' AND a.STATUS = 'VALIDATED')
  AND NOT EXISTS (SELECT 1 FROM APPLICATION_COMPLIANCE f WHERE f.LOAD_BATCH_ID = 'MOCK_V1_20261103');
-- Expected: 11399 rows inserted. A second run inserts 0.

-- 9.4 Record the outcome. PROMOTED only when every staged row is accounted for (final + rejected = staged).
UPDATE DATASET_LOAD_AUDIT
SET ROWS_FINAL    = (SELECT COUNT(*) FROM APPLICATION_COMPLIANCE   WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
    ROWS_REJECTED = (SELECT COUNT(*) FROM DATASET_REJECTED_ROWS    WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103'),
    STATUS        = 'PROMOTED',
    UPDATED_AT    = CURRENT_TIMESTAMP()
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND STATUS = 'VALIDATED'
  AND (SELECT COUNT(*) FROM APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103')
    + (SELECT COUNT(*) FROM DATASET_REJECTED_ROWS  WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103')
    = (SELECT COUNT(*) FROM STG_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103');
-- Expected: 1 row updated. 0 rows updated: counts do not add up. STOP and run script 10 to see where rows went.

-- Checkpoint 09
SELECT (SELECT COUNT(*) FROM APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS final_rows,    -- Expected 11399
       (SELECT COUNT(*) FROM DATASET_REJECTED_ROWS  WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS rejected_rows; -- Expected 0


-- ##################### 10_reconciliation.sql #####################
-- =====================================================================================
-- 10_reconciliation.sql
-- Proves the final table matches the raw file: counts, keys, per-month counts, value totals and a row-level hash.
-- Read-only except the last UPDATE of the audit status. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 10.1 Counts across the layers.
SELECT
    (SELECT COUNT(*) FROM RAW_APPLICATION_COMPLIANCE   WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS raw_rows,        -- Expected 11399
    (SELECT COUNT(*) FROM STG_APPLICATION_COMPLIANCE   WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS stg_rows,        -- Expected 11399
    (SELECT COUNT(*) FROM APPLICATION_COMPLIANCE       WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS final_rows,      -- Expected 11399
    (SELECT COUNT(*) FROM DATASET_REJECTED_ROWS        WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') AS rejected_rows;   -- Expected 0

-- 10.2 Keys: no duplicates, no missing rows.
SELECT COUNT(*) AS rows_total, COUNT(DISTINCT OBSERVATION_KEY) AS distinct_keys,   -- Expected 11399 and 11399
       COUNT(DISTINCT EON_ID) AS applications,                                       -- Expected 1500
       COUNT(DISTINCT METRIC_ID) AS metrics,                                         -- Expected 24
       COUNT(DISTINCT REPORTING_MONTHEND_DATE) AS months,                            -- Expected 12
       MIN(REPORTING_MONTHEND_DATE) AS first_month, MAX(REPORTING_MONTHEND_DATE) AS last_month  -- Expected 2025-11-30 and 2026-10-31
FROM APPLICATION_COMPLIANCE;

-- 10.3 Lost or invented rows between raw and final, by file row number. Both queries must return 0 rows.
SELECT r.SOURCE_FILE_ROW_NUMBER AS raw_row_missing_from_final
FROM RAW_APPLICATION_COMPLIANCE r
LEFT JOIN APPLICATION_COMPLIANCE f ON f.LOAD_BATCH_ID = r.LOAD_BATCH_ID AND f.SOURCE_FILE_ROW_NUMBER = r.SOURCE_FILE_ROW_NUMBER
LEFT JOIN DATASET_REJECTED_ROWS q ON q.LOAD_BATCH_ID = r.LOAD_BATCH_ID AND q.SOURCE_FILE_ROW_NUMBER = r.SOURCE_FILE_ROW_NUMBER
WHERE r.LOAD_BATCH_ID = 'MOCK_V1_20261103' AND f.SOURCE_FILE_ROW_NUMBER IS NULL AND q.SOURCE_FILE_ROW_NUMBER IS NULL;

SELECT f.SOURCE_FILE_ROW_NUMBER AS final_row_without_raw
FROM APPLICATION_COMPLIANCE f
LEFT JOIN RAW_APPLICATION_COMPLIANCE r ON r.LOAD_BATCH_ID = f.LOAD_BATCH_ID AND r.SOURCE_FILE_ROW_NUMBER = f.SOURCE_FILE_ROW_NUMBER
WHERE f.LOAD_BATCH_ID = 'MOCK_V1_20261103' AND r.SOURCE_FILE_ROW_NUMBER IS NULL;

-- 10.4 Rows per month must equal the generator's per-month counts (taken from the delivered CSV).
WITH expected(m, n) AS (
    SELECT * FROM VALUES
        ('2025-11-30'::DATE, 699),
        ('2025-12-31'::DATE, 763),
        ('2026-01-31'::DATE, 827),
        ('2026-02-28'::DATE, 859),
        ('2026-03-31'::DATE, 908),
        ('2026-04-30'::DATE, 943),
        ('2026-05-31'::DATE, 978),
        ('2026-06-30'::DATE, 1046),
        ('2026-07-31'::DATE, 1068),
        ('2026-08-31'::DATE, 1117),
        ('2026-09-30'::DATE, 1095),
        ('2026-10-31'::DATE, 1096)
)
SELECT e.m AS reporting_monthend_date, e.n AS expected_rows, COALESCE(f.n, 0) AS actual_rows,
       IFF(COALESCE(f.n, 0) = e.n, 'PASS', 'FAIL') AS status
FROM expected e
LEFT JOIN (SELECT REPORTING_MONTHEND_DATE AS m, COUNT(*) AS n FROM APPLICATION_COMPLIANCE GROUP BY 1) f ON f.m = e.m
ORDER BY e.m;
-- Expected: 12 rows, all PASS.

-- 10.5 Value totals: raw text vs final typed. All differences must be 0.
SELECT
    (SELECT SUM(TRY_TO_NUMBER(IS_NUMERATOR))   FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') - (SELECT SUM(IS_NUMERATOR)   FROM APPLICATION_COMPLIANCE) AS diff_numerator,   -- totals: 4725
    (SELECT SUM(TRY_TO_NUMBER(IS_DENOMINATOR)) FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') - (SELECT SUM(IS_DENOMINATOR) FROM APPLICATION_COMPLIANCE) AS diff_denominator, -- totals: 9106
    (SELECT SUM(TRY_TO_NUMBER(RFB))            FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') - (SELECT SUM(RFB)            FROM APPLICATION_COMPLIANCE) AS diff_rfb,         -- total: 10264
    (SELECT SUM(TRY_TO_NUMBER(TOTAL_RFB))      FROM RAW_APPLICATION_COMPLIANCE WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103') - (SELECT SUM(TOTAL_RFB)      FROM APPLICATION_COMPLIANCE) AS diff_total_rfb;   -- total: 24504 (row sum; repeated per app-month, do not use as a metric)

-- 10.6 Row-level fingerprint: raw text of key and status columns vs final typed values. Must be 0.
SELECT COUNT(*) AS rows_that_differ
FROM RAW_APPLICATION_COMPLIANCE r
JOIN APPLICATION_COMPLIANCE f ON f.LOAD_BATCH_ID = r.LOAD_BATCH_ID AND f.SOURCE_FILE_ROW_NUMBER = r.SOURCE_FILE_ROW_NUMBER
WHERE r.LOAD_BATCH_ID = 'MOCK_V1_20261103'
  AND HASH(r.METRIC_ID, r.METRIC_DATE, r.EON_ID, r.TEST_STATUS, r.TEST_RESULT, r.COMPLIANCE_STATUS, r.COMPLIANCE_REASON, r.RTO_CHANGE_DATE, r.REPORTING_MONTHEND_DATE, r.LEGAL_ENTITY_CODE, r.COST_CENTER_CODE)
   <> HASH(f.METRIC_ID, TO_CHAR(f.METRIC_DATE, 'YYYY-MM-DD'), f.EON_ID, f.TEST_STATUS, f.TEST_RESULT, f.COMPLIANCE_STATUS, f.COMPLIANCE_REASON, TO_CHAR(f.RTO_CHANGE_DATE, 'YYYY-MM-DD'), TO_CHAR(f.REPORTING_MONTHEND_DATE, 'YYYY-MM-DD'), f.LEGAL_ENTITY_CODE, f.COST_CENTER_CODE);
-- Expected: 0.

-- 10.7 Close the batch. RECONCILED only when counts, per-month checks and totals are exact and nothing was rejected.
--      If rows were rejected the status is RECONCILED_WITH_REJECTS: that is a visible warning, not a success.
UPDATE DATASET_LOAD_AUDIT
SET STATUS = IFF(ROWS_REJECTED = 0, 'RECONCILED', 'RECONCILED_WITH_REJECTS'),
    NOTES = COALESCE(NOTES, '') || ' | reconciled ' || TO_VARCHAR(CURRENT_TIMESTAMP()),
    UPDATED_AT = CURRENT_TIMESTAMP()
WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103' AND STATUS = 'PROMOTED'
  AND ROWS_FINAL + ROWS_REJECTED = ROWS_STG AND ROWS_STG = ROWS_RAW AND ROWS_FINAL = 11399;
SELECT * FROM DATASET_LOAD_AUDIT WHERE LOAD_BATCH_ID = 'MOCK_V1_20261103';
-- Checkpoint 10: STATUS = RECONCILED, ROWS_RAW = ROWS_STG = ROWS_FINAL = 11399, ROWS_REJECTED = 0.


-- ##################### 11_create_curated_views.sql #####################
-- =====================================================================================
-- 11_create_curated_views.sql
-- V_APPLICATION_MONTH_STATUS : one row per application per reporting month (the application-level grain).
-- Status: UNEXECUTED.
-- Why a view and not a dimension table: application attributes are stable inside one application-month
-- (verified: 0 of 9,784 app-months vary) but a small share of applications change attributes between months
-- (organisation, owner, tier, ...), so a one-row-per-application table would hide history.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

CREATE OR REPLACE VIEW V_APPLICATION_MONTH_STATUS
COMMENT = 'One row per application (EON_ID) per reporting month: application attributes as of that month plus application-level compliance flags. Use this for application counts and findings; use APPLICATION_COMPLIANCE for metric-row analysis.'
AS
WITH app_month AS (
    SELECT
        EON_ID,
        REPORTING_MONTHEND_DATE,
        ANY_VALUE(BUILDING_NAME) AS BUILDING_NAME,
    ANY_VALUE(EVENT_LOCATION) AS EVENT_LOCATION,
    ANY_VALUE(APPLICATION_TIER) AS APPLICATION_TIER,
    ANY_VALUE(RTO_CHANGE_DATE) AS RTO_CHANGE_DATE,
    ANY_VALUE(GRN) AS GRN,
    ANY_VALUE(APPLICATION_NAME) AS APPLICATION_NAME,
    ANY_VALUE(APPLICATION_RTO) AS APPLICATION_RTO,
    ANY_VALUE(HAS_CTIRICAL_KBS) AS HAS_CTIRICAL_KBS,
    ANY_VALUE(LIFECYCLE_PHASE) AS LIFECYCLE_PHASE,
    ANY_VALUE(ASSET_RISK_RATING_2) AS ASSET_RISK_RATING_2,
    ANY_VALUE(ARR_AVAILABILITY) AS ARR_AVAILABILITY,
    ANY_VALUE(ARR_CONFIDENTIALITY) AS ARR_CONFIDENTIALITY,
    ANY_VALUE(ARR_INTEGRITY) AS ARR_INTEGRITY,
    ANY_VALUE(IS_MERGERS_ACQUISITIONS_ASSET) AS IS_MERGERS_ACQUISITIONS_ASSET,
    ANY_VALUE(ACQUIRED_ENTITY) AS ACQUIRED_ENTITY,
    ANY_VALUE(BU_SUPER_DIVISION) AS BU_SUPER_DIVISION,
    ANY_VALUE(BU_DIVISION) AS BU_DIVISION,
    ANY_VALUE(BU_SUPER_DEPARTMENT) AS BU_SUPER_DEPARTMENT,
    ANY_VALUE(BU_DEPARTMENT) AS BU_DEPARTMENT,
    ANY_VALUE(ORG_GROUP_TYPE) AS ORG_GROUP_TYPE,
    ANY_VALUE(SUPER_DIVISION) AS SUPER_DIVISION,
    ANY_VALUE(DIVISION) AS DIVISION,
    ANY_VALUE(SUPER_DEPARTMENT) AS SUPER_DEPARTMENT,
    ANY_VALUE(DEPARTMENT) AS DEPARTMENT,
    ANY_VALUE(BUS_ORG_LG_NM) AS BUS_ORG_LG_NM,
    ANY_VALUE(COST_CENTER_CODE) AS COST_CENTER_CODE,
    ANY_VALUE(COST_CENTER_NAME) AS COST_CENTER_NAME,
    ANY_VALUE(EMPLOYEE_BUILDING_NAME) AS EMPLOYEE_BUILDING_NAME,
    ANY_VALUE(EMPLOYEE_COUNTRY_NAME) AS EMPLOYEE_COUNTRY_NAME,
    ANY_VALUE(PRIMARY_BUS_FIRST_NAME) AS PRIMARY_BUS_FIRST_NAME,
    ANY_VALUE(PRIMARY_BUS_LAST_NAME) AS PRIMARY_BUS_LAST_NAME,
    ANY_VALUE(PRIMARY_IT_FIRST_NAME) AS PRIMARY_IT_FIRST_NAME,
    ANY_VALUE(PRIMARY_IT_LAST_NAME) AS PRIMARY_IT_LAST_NAME,
    ANY_VALUE(LEGAL_ENTITY_CODE) AS LEGAL_ENTITY_CODE,
    ANY_VALUE(LEGAL_ENTITY_NAME) AS LEGAL_ENTITY_NAME,
    ANY_VALUE(IS_USBANKS) AS IS_USBANKS,
    ANY_VALUE(IS_MSBNA) AS IS_MSBNA,
    ANY_VALUE(IS_MSPBNA) AS IS_MSPBNA,
    ANY_VALUE(USBANKS_LE_LIST) AS USBANKS_LE_LIST,
    ANY_VALUE(KBS_FLAG_FLAG) AS KBS_FLAG_FLAG,
    ANY_VALUE(REPORTING_MONTH) AS REPORTING_MONTH,
    ANY_VALUE(REPORTING_YEAR) AS REPORTING_YEAR,
        COUNT(*)                                        AS METRIC_ROWS,
        COUNT(DISTINCT METRIC_ID)                       AS METRICS_REPORTED,
        COUNT_IF(COMPLIANCE_STATUS = 'Non_Compliant')   AS NON_COMPLIANT_ROWS,
        COUNT_IF(TEST_STATUS = 'Test_Complete')         AS COMPLETED_TEST_ROWS,
        COUNT_IF(TEST_STATUS = 'Test_Complete' AND TEST_RESULT = 'Fail') AS FAILED_TEST_ROWS,
        MAX(TOTAL_RFB)                                  AS OPEN_FINDINGS   -- TOTAL_RFB repeats on every metric row of the app-month: take it ONCE
    FROM APPLICATION_COMPLIANCE
    GROUP BY EON_ID, REPORTING_MONTHEND_DATE
),
flagged AS (
    SELECT a.*,
           IFF(NON_COMPLIANT_ROWS > 0, 1, 0)  AS IS_NON_COMPLIANT_APP,
           IFF(COMPLETED_TEST_ROWS = 0, 1, 0) AS HAS_NO_COMPLETED_TEST,
           IFF(FAILED_TEST_ROWS > 0, 1, 0)    AS HAS_FAILED_TEST
    FROM app_month a
),
lagged AS (
    SELECT f.*,
           LAG(REPORTING_MONTHEND_DATE) OVER (PARTITION BY EON_ID ORDER BY REPORTING_MONTHEND_DATE) AS PREV_OBSERVED_MONTH,
           LAG(IS_NON_COMPLIANT_APP)    OVER (PARTITION BY EON_ID ORDER BY REPORTING_MONTHEND_DATE) AS PREV_IS_NON_COMPLIANT_APP
    FROM flagged f
)
SELECT
    l.* EXCLUDE (PREV_IS_NON_COMPLIANT_APP),
    -- PROVISIONAL movement definition: compares an application with the IMMEDIATELY PRECEDING calendar month only.
    CASE
        WHEN l.PREV_OBSERVED_MONTH IS DISTINCT FROM LAST_DAY(DATEADD('month', -1, l.REPORTING_MONTHEND_DATE)) THEN 'NO_PRIOR_MONTH'
        WHEN l.IS_NON_COMPLIANT_APP = 1 AND l.PREV_IS_NON_COMPLIANT_APP = 0 THEN 'NEWLY_NON_COMPLIANT'
        WHEN l.IS_NON_COMPLIANT_APP = 0 AND l.PREV_IS_NON_COMPLIANT_APP = 1 THEN 'RESOLVED'
        WHEN l.IS_NON_COMPLIANT_APP = 1 AND l.PREV_IS_NON_COMPLIANT_APP = 1 THEN 'PERSISTENT_NON_COMPLIANT'
        ELSE 'NOT_NON_COMPLIANT_BOTH_MONTHS'
    END AS MOVEMENT_STATUS
FROM lagged l;

-- Checkpoint 11
SELECT COUNT(*) AS app_months,                                  -- Expected 9784
       COUNT(DISTINCT EON_ID) AS applications,                  -- Expected 1500
       COUNT(*) - COUNT(DISTINCT EON_ID || '|' || TO_CHAR(REPORTING_MONTHEND_DATE)) AS duplicate_app_months  -- Expected 0
FROM V_APPLICATION_MONTH_STATUS;

SELECT REPORTING_MONTHEND_DATE,
       COUNT(*)                                  AS applications_reporting,
       SUM(IS_NON_COMPLIANT_APP)                 AS non_compliant_apps,
       COUNT_IF(MOVEMENT_STATUS = 'NEWLY_NON_COMPLIANT') AS newly_non_compliant,
       COUNT_IF(MOVEMENT_STATUS = 'RESOLVED')            AS resolved
FROM V_APPLICATION_MONTH_STATUS
WHERE REPORTING_MONTHEND_DATE = '2026-10-31'
GROUP BY 1;
-- Expected for 2026-10-31: applications_reporting 923, non_compliant_apps 300,
--                          newly_non_compliant 132, resolved 117


-- ##################### 12_create_semantic_view.sql #####################
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
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
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
    obs.system_rtc_flag   AS SYSTEM_RTC     COMMENT = 'PROVISIONAL. 0/1 flag. Meaning not supplied by the client; do not interpret beyond the raw flag.',
    app_month.open_findings_value AS OPEN_FINDINGS COMMENT = 'PROVISIONAL. Findings (TOTAL_RFB) for ONE application in ONE month, taken once per application-month. Add across applications for a single month only.'
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
SHOW SEMANTIC DIMENSIONS IN SEMANTIC VIEW METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1;
SHOW SEMANTIC METRICS    IN SEMANTIC VIEW METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1;
-- If CREATE SEMANTIC VIEW fails with a syntax error, STOP. Capture the full error text and the line it points to.
-- The most likely adjustments (account feature differences, see SEMANTIC_MODEL.md "Syntax risk list") are listed there.


-- ##################### 13_create_agent.sql #####################
-- =====================================================================================
-- 13_create_agent.sql
-- Cortex Agent METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 with one Cortex Analyst tool bound to
-- the semantic view. Status: UNEXECUTED (field names taken from the CREATE AGENT documentation; see AGENT_CONFIGURATION.md).
-- IF NOT EXISTS: re-running does not overwrite. To change a live agent use the ALTER block at the bottom.
-- BEFORE RUNNING: replace <WAREHOUSE_NAME> inside the specification below (it appears once) with a real warehouse name.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

CREATE AGENT IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1
  COMMENT = 'Analyses the synthetic application compliance dataset through the SV_APPLICATION_COMPLIANCE_V1 semantic view.'
  PROFILE = '{"display_name": "Application Compliance Analyst"}'
  FROM SPECIFICATION
  $$
    # Cortex Agent specification for AGENT_APPLICATION_COMPLIANCE_V1 (UNEXECUTED; field names per the CREATE AGENT docs).
    # Replace <WAREHOUSE_NAME> with the warehouse Cortex Analyst should use. Nothing else needs editing.
    models:
      orchestration: auto

    orchestration:
      budget:
        seconds: 60
        tokens: 16000

    instructions:
      response: |
        Be concise and numerate. Lead with the answer, then the supporting figures, then any caveat.
        Always state the reporting period used (a month-end date). If the user gave none, use 2026-10-31 and say so.
        Give counts with their population (for example "300 of 923 applications") so the reader can judge scale.
        Mark any measure that is provisional as "provisional" in the sentence where it appears.
        Never describe a tier, risk code or RTO band as higher, lower, worse or more critical: these codes have no defined direction here.
        Present tables for lists of more than three items. Do not invent business definitions, targets, thresholds or SLAs.
        All names in this dataset are synthetic; never imply they refer to real people or organisations.
      orchestration: |
        Use the analyst tool for every question about this dataset. Do not answer numeric questions from memory.
        If the question needs a definition the model does not hold (metric names, severity, thresholds, regulations), say so and offer what the data can show.
        If "compliance rate" or "percentage" is requested, answer with the provisional rate and its numerator and denominator, labelled provisional.
        If "critical", "high risk" or "worst" is used, ask whether to rank by non-compliant applications, failed tests or open findings instead.
        If a question could mean either organisation hierarchy, use the business organisation hierarchy (super division, division) unless the user says BU or business unit.
        Ask one short clarifying question only when the answer would change materially; otherwise state the assumption and proceed.
      sample_questions:
        - question: "How many applications are non-compliant in the latest month?"
          answer: "Counts distinct applications with at least one Non_Compliant metric row for 2026-10-31."
        - question: "Which super divisions have the most non-compliant applications this month?"
          answer: "Ranks super divisions by non-compliant applications with the share of applications reporting."
        - question: "Which applications became newly non-compliant compared with last month?"
          answer: "Lists applications whose movement status is NEWLY_NON_COMPLIANT (provisional definition)."
        - question: "Show the trend of non-compliant applications over the last 12 months."
          answer: "Monthly count of non-compliant applications and applications reporting."
        - question: "How many applications have no completed test this month?"
          answer: "Counts applications with no Test_Complete row for 2026-10-31."

    tools:
      - tool_spec:
          type: cortex_analyst_text_to_sql
          name: ApplicationComplianceAnalyst
          description: |
            Answers questions about application compliance, testing, findings, organisation, legal entity, owners and monthly
            trends from the synthetic enterprise dataset (1,500 applications, 24 metrics, 12 month-ends 2025-11-30 to 2026-10-31).
            Use for any counting, ranking, trend or comparison question. Application counts come from application-month level
            measures; metric-row counts come from observation-level measures. Several measures are provisional.

    tool_resources:
      ApplicationComplianceAnalyst:
        semantic_view: "METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1"
        execution_environment:
          type: warehouse
          warehouse: "<WAREHOUSE_NAME>"
          query_timeout: 120
  $$;

-- Checkpoint 13
SHOW AGENTS IN SCHEMA METRICS_ANALYZER.MOCK_DATA;            -- Expected: AGENT_APPLICATION_COMPLIANCE_V1
DESCRIBE AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1;
-- Expected: the specification shows one tool ApplicationComplianceAnalyst and the semantic view name.
-- If CREATE AGENT fails: STOP and capture the error text. Typical causes: Cortex Agents not enabled for the account/region,
-- missing CREATE AGENT privilege on the schema, or a specification field name that differs in your account's release.

-- ---- Upgrade path (do NOT run on first install): replaces the live specification, keeps the object and its grants ----
-- ALTER AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 MODIFY LIVE VERSION SET SPECIFICATION =
-- $$ ...complete new specification... $$;


-- ##################### 14_grant_permissions.sql #####################
-- =====================================================================================
-- 14_grant_permissions.sql
-- Minimal-privilege read access for ONE role: METRICS_ANALYZER_DEMO_VIEWER. Touches only the MOCK_DATA objects created here.
-- Nothing on METRICS_ANALYZER.DQ is granted. Status: UNEXECUTED. Run as a role that owns the objects (or SECURITYADMIN for the role).
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 14.1 The viewer role (skip if your organisation already has an equivalent role: replace the name everywhere in this file).
CREATE ROLE IF NOT EXISTS METRICS_ANALYZER_DEMO_VIEWER COMMENT = 'Read-only access to METRICS_ANALYZER.MOCK_DATA demo objects and the compliance agent.';

-- 14.2 Container and compute access.
GRANT USAGE ON DATABASE METRICS_ANALYZER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT USAGE ON SCHEMA   METRICS_ANALYZER.MOCK_DATA TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT USAGE ON WAREHOUSE IDENTIFIER($WH_NAME) TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.3 Data the agent reads. Cortex Analyst runs with the caller's rights, so the caller needs SELECT on the semantic view
--      and on the objects behind it.
GRANT SELECT ON TABLE METRICS_ANALYZER.MOCK_DATA.APPLICATION_COMPLIANCE        TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT SELECT ON VIEW  METRICS_ANALYZER.MOCK_DATA.V_APPLICATION_MONTH_STATUS    TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT SELECT ON SEMANTIC VIEW METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.4 The agent.
GRANT USAGE ON AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.5 Not granted on purpose: raw, staging, audit, rejected-row tables, the stage, and anything in DQ.
--      The viewer cannot see unvalidated data or load history.

-- ---- Optional B: Cortex entitlement. Run ONLY if SHOW GRANTS (in 00_preflight) showed PUBLIC lacks SNOWFLAKE.CORTEX_USER ----
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
-- If your release exposes the agent-specific database role, grant that instead / as well (confirm the name in PERMISSIONS.md):
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- ---- Optional C: let the viewer monitor the agent's threads/traces. Syntax UNVERIFIED: confirm in the docs before use ----
-- GRANT MONITOR ON AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- ---- Administrator-only note (NOT a script step) ----
-- If the account's region does not host the model Cortex needs, an ACCOUNTADMIN may have to set CORTEX_ENABLED_CROSS_REGION.
-- This script never changes account parameters. See PERMISSIONS.md.

-- 14.6 Give the role to the people who should use the demo (replace <USER_NAME>; one statement per user).
-- GRANT ROLE METRICS_ANALYZER_DEMO_VIEWER TO USER <USER_NAME>;

-- Checkpoint 14
SHOW GRANTS TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
-- Expected: USAGE on the database, schema, warehouse and agent; SELECT on the table, view and semantic view; nothing on DQ.


-- ##################### 15_smoke_tests.sql #####################
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

