# Data Quality Snowflake scripts

Executable scripts for the approved contract in `DQ_SNOWFLAKE_CONTRACT.md` (parent of this repo). The FastAPI service reads the database these scripts build. Run them again only when reseeding or changing the schema.

Run in one session, in this order:

1. `01_create_database_and_schema.sql`
2. `02_create_tables.sql`
3. `03_create_staging_tables.sql`
4. The CSV load below
5. `04_reseed_and_snapshot.sql`
6. `05_validate_data.sql`
7. `06_semantic_view.sql` (any time after step 2)

`04` reads staging, replaces the seven source tables, merges `DQ_CONTROL_SNAPSHOT`, and only then updates the single `DQ_DATASET_STATE` row, immediately before `COMMIT`. Each control keeps its own `CONTROL_DATA_VERSION`: an existing snapshot row increments by 1, and a new control starts at 1. `ACTIVE_DATASET_VERSION` still increments for the whole dataset. A failed preflight does not open that transaction. A failure after `BEGIN TRANSACTION` rolls it back, so the active dataset version and the control versions stay on the previous published rows.

Do not re-run `03` between the CSV load and `04`. `CREATE OR REPLACE` on the transient staging tables drops the load.

Database `METRICS_ANALYZER` and schema `DQ` are the names these scripts use. The contract does not choose them. No warehouse is created.

## CSV files

Export these sheets from `SMARTS_DQ_mock_data.xlsx` to UTF-8 CSV. Keep the header row. Keep the sheet column order. Excel should quote fields that contain commas.

Before Save As CSV, format every date column as `yyyy-mm-dd`. That cell formatting is mandatory. The CSV must contain ISO `YYYY-MM-DD` text. This COPY workflow does not accept a raw Excel serial such as `46237`, and it does not accept a locale date such as `03/08/2026`.

| File | Date column | Required CSV text |
| --- | --- | --- |
| `dq_results.csv` | `metric_date` | `YYYY-MM-DD` |
| `dq_results_by_desk.csv` | `metric_date` | `YYYY-MM-DD` |
| `dq_exceptions.csv` | `exception_date` | `YYYY-MM-DD` |
| `analyst_commentary.csv` | `commentary_date` | `YYYY-MM-DD` |
| `change_incident_events.csv` | `event_date` | `YYYY-MM-DD` |

Each date COPY keeps a value only when the trimmed text matches `____-__-__`, then calls `TRY_TO_DATE` with no format argument. An impossible date such as `2026-02-31` becomes NULL. Any other text becomes NULL. The NOT NULL date column then rejects the row.

`PLANTED_STORY` is not a column on `dq_control_definitions`. Do not load the README sheet into that table. Save the five README `planted_story` cells, with no period prefix and no added trailing period, as `planted_story.csv`:

```csv
control_id,planted_story
DQ-001,"LEI nulls after onboarding migration; Equity Derivatives and Prime Services are the hotspots"
DQ-010,"UTI mismatch after TR vendor schema change and duplicate UTI hotfix; Rates and Credit are the hotspots"
DQ-015,"Scheduler failure caused late T+1 submissions on all desks; partial recovery 26-27 Oct"
DQ-020,"Commodities booking migration not mapped to risk feed; Commodities and Securitised are the hotspots"
DQ-025,"Gradual drift: vendor ISIN feed delayed; Equities Cash and Treasury are the hotspots"
```

The longest story is DQ-010, 102 characters. The other 31 controls stay null.

## Upload

Snowsight: open the `DQ_CSV_STAGE` stage created by script 03 and add the eight CSV files.

SnowSQL, from the directory that contains the files:

```text
PUT file://dq_control_definitions.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://dq_results.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://dq_results_by_desk.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://dq_exceptions.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://desk_hierarchy.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://change_incident_events.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://analyst_commentary.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT file://planted_story.csv @METRICS_ANALYZER.DQ.DQ_CSV_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
```

## Load into staging

Run this after script 03 and the upload, and before script 04. It is DML against transient staging only. Thresholds and pass rates use `TRY_TO_DECIMAL` at `NUMBER(18,4)`. Volume share uses `NUMBER(8,4)`. Record counts use `NUMBER(18,0)`. Ageing days use `NUMBER(6,0)`. RAG tokens stay `Green`, `Amber`, and `Red`. The SELECT list uses only functions Snowflake documents for COPY transformations: `CASE`, `LIKE`, `TRIM`, `TRY_TO_DATE`, and `TRY_TO_DECIMAL`.

```sql
USE DATABASE METRICS_ANALYZER;
USE SCHEMA DQ;

COPY INTO STG_DQ_CONTROL_DEFINITIONS (
  CONTROL_ID, CONTROL_NAME, DQ_DIMENSION, REGULATION, REGULATORY_REPORT,
  CRITICAL_DATA_ELEMENT, SOURCE_SYSTEM, FREQUENCY, GREEN_THRESHOLD,
  AMBER_THRESHOLD, SEVERITY, CHECK_LOGIC, BCBS239_PRINCIPLE, OWNER_ROLE,
  PLANTED_STORY
)
FROM (
  SELECT
    $1, $2, $3, $4, $5, $6, $7, $8,
    TRY_TO_DECIMAL($9, 18, 4),
    TRY_TO_DECIMAL($10, 18, 4),
    $11, $12, $13, $14,
    NULL
  FROM @DQ_CSV_STAGE/dq_control_definitions.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_DESK_HIERARCHY
FROM (
  SELECT $1, $2, $3, $4, TRY_TO_DECIMAL($5, 8, 4)
  FROM @DQ_CSV_STAGE/desk_hierarchy.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_DQ_RESULTS
FROM (
  SELECT
    $1,
    CASE
      WHEN TRIM($2) LIKE '____-__-__'
      THEN TRY_TO_DATE(TRIM($2))
      ELSE NULL
    END,
    $3, $4,
    TRY_TO_DECIMAL($5, 18, 0),
    TRY_TO_DECIMAL($6, 18, 0),
    TRY_TO_DECIMAL($7, 18, 4),
    $8
  FROM @DQ_CSV_STAGE/dq_results.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_DQ_RESULTS_BY_DESK
FROM (
  SELECT
    $1,
    CASE
      WHEN TRIM($2) LIKE '____-__-__'
      THEN TRY_TO_DATE(TRIM($2))
      ELSE NULL
    END,
    $3, $4,
    TRY_TO_DECIMAL($5, 18, 0),
    TRY_TO_DECIMAL($6, 18, 0),
    TRY_TO_DECIMAL($7, 18, 4),
    $8
  FROM @DQ_CSV_STAGE/dq_results_by_desk.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_DQ_EXCEPTIONS
FROM (
  SELECT
    $1,
    CASE
      WHEN TRIM($2) LIKE '____-__-__'
      THEN TRY_TO_DATE(TRIM($2))
      ELSE NULL
    END,
    $3, $4, $5, $6, $7, $8, $9, $10,
    TRY_TO_DECIMAL($11, 6, 0),
    $12
  FROM @DQ_CSV_STAGE/dq_exceptions.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_CHANGE_INCIDENT_EVENTS
FROM (
  SELECT
    $1,
    CASE
      WHEN TRIM($2) LIKE '____-__-__'
      THEN TRY_TO_DATE(TRIM($2))
      ELSE NULL
    END,
    $3, $4, $5, $6
  FROM @DQ_CSV_STAGE/change_incident_events.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

COPY INTO STG_ANALYST_COMMENTARY
FROM (
  SELECT
    CASE
      WHEN TRIM($1) LIKE '____-__-__'
      THEN TRY_TO_DATE(TRIM($1))
      ELSE NULL
    END,
    $2, $3, $4, $5, $6, $7
  FROM @DQ_CSV_STAGE/analyst_commentary.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

CREATE OR REPLACE TEMPORARY TABLE STG_PLANTED_STORY (
  CONTROL_ID VARCHAR(16),
  PLANTED_STORY VARCHAR(256)
);

COPY INTO STG_PLANTED_STORY
FROM (
  SELECT $1, $2
  FROM @DQ_CSV_STAGE/planted_story.csv
)
FILE_FORMAT = (FORMAT_NAME = 'DQ_CSV_FORMAT')
FORCE = FALSE
ON_ERROR = 'ABORT_STATEMENT';

UPDATE STG_DQ_CONTROL_DEFINITIONS AS definition
SET PLANTED_STORY = story.PLANTED_STORY
FROM STG_PLANTED_STORY AS story
WHERE definition.CONTROL_ID = story.CONTROL_ID;

SELECT 'STG_DQ_CONTROL_DEFINITIONS' AS staging_table, COUNT(*) AS rows_loaded, 36 AS expected FROM STG_DQ_CONTROL_DEFINITIONS
UNION ALL SELECT 'STG_DQ_RESULTS', COUNT(*), 1722 FROM STG_DQ_RESULTS
UNION ALL SELECT 'STG_DQ_RESULTS_BY_DESK', COUNT(*), 4536 FROM STG_DQ_RESULTS_BY_DESK
UNION ALL SELECT 'STG_DQ_EXCEPTIONS', COUNT(*), 1560 FROM STG_DQ_EXCEPTIONS
UNION ALL SELECT 'STG_DESK_HIERARCHY', COUNT(*), 9 FROM STG_DESK_HIERARCHY
UNION ALL SELECT 'STG_CHANGE_INCIDENT_EVENTS', COUNT(*), 12 FROM STG_CHANGE_INCIDENT_EVENTS
UNION ALL SELECT 'STG_ANALYST_COMMENTARY', COUNT(*), 12 FROM STG_ANALYST_COMMENTARY
UNION ALL SELECT 'STG_PLANTED_STORY', COUNT(*), 5 FROM STG_PLANTED_STORY;
```

`STG_PLANTED_STORY` is a temporary table for this load. It is not one of the seven staging tables and it is not published.

Column positions follow the workbook headers, left to right. `$1` is the first column after the header is skipped. Do not run `04` until the count query matches every expected value and each COPY result shows `rows_loaded` greater than zero.

## Retry a COPY

Snowflake remembers files already loaded into a table for 64 days. `TRUNCATE` and `DELETE` do not clear that memory. A second `COPY` of the same file, with `FORCE = FALSE`, loads zero rows and leaves the truncated table empty. That is a failed retry. Do not continue to `04`.

A COPY that errors does not record the file as loaded, so that statement can be run again.

Safe full retry:

1. Run `03_create_staging_tables.sql` again. `CREATE OR REPLACE` builds new transient tables, and those new tables have empty load history.
2. `PUT` the files again if they are not already on the stage.
3. Run every `COPY` in this section from the top, still with `FORCE = FALSE`.
4. Run the count query. Continue to `04` only when every count matches.

Do not use `FORCE = TRUE` while a staging table still has rows. `FORCE` loads the file again even when history says it was loaded, and it would duplicate those rows. Recreating the tables in step 1 is the path that avoids both a silent empty load and a duplicate load.

## Cache lookup

The API uses this after a reseed. The cache key is the current snapshot's `CONTROL_DATA_VERSION`, plus `ANALYSIS_TYPE`, `PROMPT_VERSION`, `CALCULATION_VERSION`, and `MODEL`. `DATASET_VERSION` stays on the run as provenance and is not part of the key. Only a `COMPLETED` row whose JSON already passed validation is eligible. This query is not run by these scripts.

```sql
SELECT run.RESULT
FROM DQ_AI_ANALYSIS_RUNS run
JOIN DQ_CONTROL_SNAPSHOT snapshot
  ON snapshot.CONTROL_ID = run.CONTROL_ID
 AND snapshot.CONTROL_DATA_VERSION = run.CONTROL_DATA_VERSION
WHERE snapshot.CONTROL_ID = ?
  AND run.ANALYSIS_TYPE = ?
  AND run.PROMPT_VERSION = ?
  AND run.CALCULATION_VERSION = ?
  AND run.MODEL = ?
  AND run.STATUS = 'COMPLETED'
  AND run.RESULT IS NOT NULL
ORDER BY run.GENERATED_AT DESC
LIMIT 1;
```

A full reseed increments `CONTROL_DATA_VERSION` for every control it rebuilds, so cached runs for those controls no longer match. A later incremental load increments the version only for controls whose inputs changed. Unrelated controls keep their version, and their completed runs stay reusable. `ACTIVE_DATASET_VERSION` still increments for the dataset as a whole.
