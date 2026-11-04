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
