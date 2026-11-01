-- Cortex Analyst semantic view. Creates no tables.
-- Measures are bound to one fact table. AI_SQL_GENERATION tells Analyst not to fan out
-- failed records, pass rates, or exception counts across fact tables.
-- Validation questions stay in 05_validate_data.sql until they have been run on Snowflake.
-- Do not add AI_VERIFIED_QUERIES before that execution.

USE DATABASE METRICS_ANALYZER;
USE SCHEMA DQ;

CREATE OR REPLACE SEMANTIC VIEW SV_METRICS_ANALYZER_DQ
  TABLES (
    definitions AS DQ_CONTROL_DEFINITIONS
      PRIMARY KEY (CONTROL_ID)
      WITH SYNONYMS = ('controls', 'control definitions')
      COMMENT = 'Control catalogue. PLANTED_STORY is supplied README context, not an established fact.',
    desks AS DESK_HIERARCHY
      PRIMARY KEY (DESK_ID)
      WITH SYNONYMS = ('desk hierarchy')
      COMMENT = 'Nine desks. VOLUME_SHARE is a fraction and sums to 1.',
    results AS DQ_RESULTS
      PRIMARY KEY (RESULT_ID)
      UNIQUE (CONTROL_ID, METRIC_DATE)
      WITH SYNONYMS = ('control results', 'history')
      COMMENT = 'Historical control results. RESULT_ID uses the R sequence.',
    desk_results AS DQ_RESULTS_BY_DESK
      PRIMARY KEY (RESULT_ID)
      UNIQUE (CONTROL_ID, METRIC_DATE, DESK_ID)
      WITH SYNONYMS = ('desk split')
      COMMENT = 'Desk results. RESULT_ID uses the O sequence and does not reference results.RESULT_ID.',
    exceptions AS DQ_EXCEPTIONS
      PRIMARY KEY (EXCEPTION_ID)
      COMMENT = 'Record-level failures. Count them only from this table.',
    events AS CHANGE_INCIDENT_EVENTS
      PRIMARY KEY (EVENT_ID)
      COMMENT = 'DESK_IDS is a comma-separated list or the token ALL. A related control is not a cause.',
    commentary AS ANALYST_COMMENTARY
      UNIQUE (COMMENTARY_DATE, CONTROL_ID)
      COMMENT = 'Supplied notes. ROOT_CAUSE_CATEGORY and PATH_TO_GREEN are not confirmed causes or approved plans.',
    snapshot AS DQ_CONTROL_SNAPSHOT
      PRIMARY KEY (CONTROL_ID)
      WITH SYNONYMS = ('latest position', 'current status')
      COMMENT = 'One latest row per control that has results. CONTROL_DATA_VERSION increments per control. DATASET_VERSION is dataset provenance. Calculation version dq-rag-v1.'
  )
  RELATIONSHIPS (
    snapshot_to_definitions AS
      snapshot (CONTROL_ID) REFERENCES definitions (CONTROL_ID),
    results_to_definitions AS
      results (CONTROL_ID) REFERENCES definitions (CONTROL_ID),
    desk_results_to_definitions AS
      desk_results (CONTROL_ID) REFERENCES definitions (CONTROL_ID),
    desk_results_to_desks AS
      desk_results (DESK_ID) REFERENCES desks (DESK_ID),
    desk_results_to_results AS
      desk_results (CONTROL_ID, METRIC_DATE) REFERENCES results (CONTROL_ID, METRIC_DATE),
    exceptions_to_definitions AS
      exceptions (CONTROL_ID) REFERENCES definitions (CONTROL_ID),
    exceptions_to_desks AS
      exceptions (DESK_ID) REFERENCES desks (DESK_ID),
    events_to_definitions AS
      events (RELATED_CONTROL_ID) REFERENCES definitions (CONTROL_ID),
    commentary_to_definitions AS
      commentary (CONTROL_ID) REFERENCES definitions (CONTROL_ID)
  )
  FACTS (
    snapshot.pass_rate_pct AS snapshot.PASS_RATE_PCT
      COMMENT = 'Latest supplied pass rate on a 0-100 scale. Do not sum pass rates.',
    snapshot.failed_records AS snapshot.FAILED_RECORDS
      COMMENT = 'Latest failed records. Do not add historical or desk failed records to this value.',
    snapshot.total_records AS snapshot.TOTAL_RECORDS
      COMMENT = 'Latest total records for the control.',
    snapshot.open_exception_count AS snapshot.OPEN_EXCEPTION_COUNT
      COMMENT = 'Open exceptions stored at snapshot time.',
    snapshot.point_count AS snapshot.POINT_COUNT
      COMMENT = 'Number of supplied result dates. Missing dates are not filled.',
    results.failed_records AS results.FAILED_RECORDS
      COMMENT = 'Failed records for one control on one date.',
    results.total_records AS results.TOTAL_RECORDS
      COMMENT = 'Total records for one control on one date.',
    results.pass_rate_pct AS results.PASS_RATE_PCT
      COMMENT = 'Supplied pass rate for that date, 0-100 scale. Do not sum pass rates.',
    desk_results.failed_records AS desk_results.FAILED_RECORDS
      COMMENT = 'Failed records for one desk on one control-date.',
    desk_results.total_records AS desk_results.TOTAL_RECORDS
      COMMENT = 'Total records for one desk on one control-date.',
    desk_results.pass_rate_pct AS desk_results.PASS_RATE_PCT
      COMMENT = 'Supplied desk pass rate, 0-100 scale.',
    exceptions.ageing_days AS exceptions.AGEING_DAYS
      COMMENT = 'Supplied ageing days. Do not derive this from the exception date.',
    desks.volume_share AS desks.VOLUME_SHARE
      COMMENT = 'Fraction of book volume. Sum only across desks.'
  )
  DIMENSIONS (
    definitions.control_id AS definitions.CONTROL_ID WITH SYNONYMS = ('control'),
    definitions.control_name AS definitions.CONTROL_NAME,
    definitions.dq_dimension AS definitions.DQ_DIMENSION WITH SYNONYMS = ('dimension', 'domain'),
    definitions.regulation AS definitions.REGULATION,
    definitions.regulatory_report AS definitions.REGULATORY_REPORT,
    definitions.critical_data_element AS definitions.CRITICAL_DATA_ELEMENT WITH SYNONYMS = ('cde'),
    definitions.source_system AS definitions.SOURCE_SYSTEM,
    definitions.frequency AS definitions.FREQUENCY,
    definitions.severity AS definitions.SEVERITY,
    definitions.owner_role AS definitions.OWNER_ROLE,
    definitions.bcbs239_principle AS definitions.BCBS239_PRINCIPLE,
    definitions.check_logic AS definitions.CHECK_LOGIC,
    definitions.green_threshold AS definitions.GREEN_THRESHOLD,
    definitions.amber_threshold AS definitions.AMBER_THRESHOLD,
    definitions.planted_story AS definitions.PLANTED_STORY
      COMMENT = 'README planted_story cell. Supplied story context, not an observed fact and not a confirmed cause.',
    desks.desk_id AS desks.DESK_ID,
    desks.desk_name AS desks.DESK_NAME,
    desks.business_line AS desks.BUSINESS_LINE,
    desks.primary_region AS desks.PRIMARY_REGION,
    snapshot.rag_status AS snapshot.RAG_STATUS WITH SYNONYMS = ('latest rag', 'current status'),
    snapshot.as_of_date AS snapshot.AS_OF_DATE WITH SYNONYMS = ('latest date'),
    snapshot.first_red_date AS snapshot.FIRST_RED_DATE,
    snapshot.last_red_date AS snapshot.LAST_RED_DATE,
    snapshot.recovered AS snapshot.RECOVERED,
    snapshot.has_desk_split AS snapshot.HAS_DESK_SPLIT,
    snapshot.control_data_version AS snapshot.CONTROL_DATA_VERSION
      COMMENT = 'Per-control version. It increments when that control is rebuilt. It is not a dataset-wide version.',
    snapshot.dataset_version AS snapshot.DATASET_VERSION
      COMMENT = 'Dataset provenance from ACTIVE_DATASET_VERSION at calculation time.',
    snapshot.calculation_version AS snapshot.CALCULATION_VERSION,
    results.metric_date AS results.METRIC_DATE,
    results.rag_status AS results.RAG_STATUS
      COMMENT = 'Historical workbook RAG. Current status comes from the snapshot.',
    results.result_id AS results.RESULT_ID
      COMMENT = 'R-sequence result id.',
    desk_results.metric_date AS desk_results.METRIC_DATE,
    desk_results.rag_status AS desk_results.RAG_STATUS,
    desk_results.result_id AS desk_results.RESULT_ID
      COMMENT = 'O-sequence id. Do not join this to results.RESULT_ID.',
    exceptions.exception_date AS exceptions.EXCEPTION_DATE,
    exceptions.status AS exceptions.STATUS,
    exceptions.severity AS exceptions.SEVERITY,
    exceptions.field_name AS exceptions.FIELD_NAME,
    events.event_date AS events.EVENT_DATE,
    events.event_type AS events.EVENT_TYPE,
    events.desk_ids AS events.DESK_IDS
      COMMENT = 'Comma-separated desk ids, or ALL. ALL is not a DESK_ID.',
    commentary.commentary_date AS commentary.COMMENTARY_DATE,
    commentary.rag_at_time AS commentary.RAG_AT_TIME,
    commentary.root_cause_category AS commentary.ROOT_CAUSE_CATEGORY
      COMMENT = 'Supplied label, not a confirmed cause.',
    commentary.path_to_green AS commentary.PATH_TO_GREEN
      COMMENT = 'Supplied path, not an approved plan.',
    commentary.author_role AS commentary.AUTHOR_ROLE,
    commentary.analyst_commentary AS commentary.ANALYST_COMMENTARY
  )
  METRICS (
    snapshot.latest_red_controls AS SUM(IFF(snapshot.RAG_STATUS = 'Red', 1, 0))
      COMMENT = 'Controls whose latest status is Red. For this workbook the value is 5. Do not count historical red rows.',
    snapshot.latest_amber_controls AS SUM(IFF(snapshot.RAG_STATUS = 'Amber', 1, 0))
      COMMENT = 'Controls whose latest status is Amber. For this workbook the value is 2.',
    snapshot.latest_green_controls AS SUM(IFF(snapshot.RAG_STATUS = 'Green', 1, 0))
      COMMENT = 'Controls whose latest status is Green. For this workbook the value is 29.',
    results.historical_red_rows AS SUM(IFF(results.RAG_STATUS = 'Red', 1, 0))
      COMMENT = 'Count of historical red result rows. This workbook has 71. This is not the current red-control count.',
    desk_results.desk_failed_records AS SUM(desk_results.FAILED_RECORDS)
      COMMENT = 'Sum of desk failed records. Aggregate this table on its own, then compare with a control total.',
    exceptions.open_exception_count AS SUM(IFF(exceptions.STATUS = 'Open', 1, 0))
      COMMENT = 'Open exceptions from DQ_EXCEPTIONS only. Do not join result dates or desks before counting. This workbook has 722.',
    desks.volume_share_sum AS SUM(desks.VOLUME_SHARE)
      COMMENT = 'Sum of desk volume shares. Valid at desk grain only. The nine desks sum to 1.'
  )
  COMMENT = 'Metrics Analyzer Data Quality semantic view. Current status is the snapshot. History is DQ_RESULTS. A linked event is not a cause.'
  AI_SQL_GENERATION '
Answer current RAG, latest pass rate, latest failed records, and latest totals from the snapshot only.
Answer history from results only.
Answer desk splits from desk_results only.
Answer exception counts from exceptions only.
Join dimensions many-to-one onto one fact table.
Do not join snapshot, results, desk_results, and exceptions together and then sum failed records, total records, pass rates, or row counts.
Pass rates are already on a 0-100 scale. Do not multiply them by 100 and do not sum them.
Volume share is a fraction. Sum it only across desks.
PLANTED_STORY, commentary, and path_to_green are supplied context. They are not established facts and they are not confirmed causes.
An event linked by related control id is not evidence that the event caused the RAG.
DESK_IDS may contain the token ALL, which means every desk and is not a desk id.
Join desk results to results on control id and metric date. Do not join the two result id sequences.
A control with no result row is absent from the snapshot and means insufficient data, not green.
Weekly controls can have an earlier as-of date than the portfolio maximum.
'
  AI_QUESTION_CATEGORIZATION '
Questions about the latest or current RAG, pass rate, or failed total use the snapshot.
Questions about a trend or an earlier date use results.
Questions about desks or hotspots use desk_results.
Questions about exceptions use exceptions.
Questions about a planted story or commentary ask for supplied context and must not treat that text as the cause.
';
