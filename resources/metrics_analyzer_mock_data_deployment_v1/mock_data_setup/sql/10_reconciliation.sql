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
