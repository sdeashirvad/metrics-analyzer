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
