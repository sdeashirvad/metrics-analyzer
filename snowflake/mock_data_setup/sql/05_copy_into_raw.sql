-- =====================================================================================
-- 05_copy_into_raw.sql
-- Loads the authoritative CSV into RAW_APPLICATION_COMPLIANCE and opens the audit record.
-- No FORCE option. No silent double load. Status: UNEXECUTED.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = 'ACCOUNTADMIN';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = 'COMPUTE_WH';      -- an existing warehouse (from 00_preflight 0.2)
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
