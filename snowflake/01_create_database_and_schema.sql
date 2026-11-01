-- Metrics Analyzer POC. Run before the other scripts in this folder.
-- Does not create a warehouse, role, tables, or Snowflake objects beyond the database and schema.
-- Names METRICS_ANALYZER and DQ are the script convention. The approved contract does not fix them.

CREATE DATABASE IF NOT EXISTS METRICS_ANALYZER
  COMMENT = 'Metrics Analyzer POC. Data Quality tables follow DQ_SNOWFLAKE_CONTRACT.md. Technology Risk is not stored here.';

CREATE SCHEMA IF NOT EXISTS METRICS_ANALYZER.DQ
  COMMENT = 'Approved DQ source tables, snapshot, analysis cache, and the single dataset-state row.';
