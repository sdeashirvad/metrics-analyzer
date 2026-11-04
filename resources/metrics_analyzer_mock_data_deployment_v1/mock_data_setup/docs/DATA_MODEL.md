# Data model

## Layers and objects (`METRICS_ANALYZER.MOCK_DATA`)

| Object | Kind | Grain / purpose |
|---|---|---|
| `CLIENT_CSV_FORMAT`, `CLIENT_CSV_FORMAT_NOHEADER` | file formats | The second is used only to read the header row in script 04 |
| `CLIENT_DATA_STAGE` | internal stage | Landing zone for the CSV |
| `RAW_APPLICATION_COMPLIANCE` | table | One row per CSV data row. **All 57 source columns as VARCHAR**, plus `SOURCE_FILE_NAME`, `SOURCE_FILE_ROW_NUMBER`, `LOAD_BATCH_ID`, `LOADED_AT`. Nothing is converted, so bad values load and can be inspected. |
| `STG_APPLICATION_COMPLIANCE` | table | Same rows, typed. `CONVERSION_ERRORS` (array) names every column whose text did not convert. |
| `APPLICATION_COMPLIANCE` | table | **Validated analytical table.** Typed, NOT NULL where the dictionary says the column is never blank, plus `OBSERVATION_KEY`, `LOAD_BATCH_ID`, `SOURCE_FILE_ROW_NUMBER`, `PROMOTED_AT`. |
| `DATASET_LOAD_AUDIT` | table | One row per batch: counts per layer and STATUS (`STARTED` → `RAW_LOADED` → `STAGED` → `VALIDATED` → `PROMOTED` → `RECONCILED`, or `RECONCILED_WITH_REJECTS` / `FAILED`) |
| `DATASET_REJECTED_ROWS` | table | Rows that failed blocking validation, with reasons and the raw record. Expected empty. |
| `V_STG_ROW_VALIDATION`, `V_STG_VALIDATION_RESULTS` | views | Row-level reject reasons and dataset-level check results (script 07) |
| `V_APPLICATION_MONTH_STATUS` | view | One row per application per month with application-level flags and movement (script 11) |
| `SV_APPLICATION_COMPLIANCE_V1` | semantic view | Cortex Analyst model over the two analytical objects |
| `AGENT_APPLICATION_COMPLIANCE_V1` | agent | Chat over the semantic view |

## Grain – what one row means

One row of `APPLICATION_COMPLIANCE` is **one application's observation of one metric at one month-end**: `EON_ID × METRIC_ID × METRIC_DATE`.
- Observed unique (11399 rows, 0 duplicate keys). The client specification allows `EON_ID` and `METRIC_ID` to repeat and a future extract could repeat the full key, so uniqueness is **checked** (scripts 07, 10), not declared – Snowflake does not enforce `PRIMARY KEY` on standard tables.
- A row is **not** an application. Application counts use `V_APPLICATION_MONTH_STATUS` (one row per application-month, 9784 rows).
- Not every application reports every month and not every application reports every metric.

## Column groups

- **Keys:** `EON_ID`, `METRIC_ID`, `METRIC_DATE` (= `REPORTING_MONTHEND_DATE` on every row).
- **Observation (13 columns):** metric/date type, numerator/denominator flags, test status/result, exemption, `RFB`, `TOTAL_RFB`, `SYSTEM_RTC`, compliance status/reason.
- **Application attributes (42 columns):** constant within an application-month (verified: 0 violations); can change between months. They repeat on every metric row of the application-month, so aggregating them from the row table over-counts.
- **Findings:** `RFB` is per row (blank on 123 rows); `TOTAL_RFB` repeats across the application-month's rows (blank on 117). Never sum `TOTAL_RFB` across rows.

## Validation rules (script 07)

*Blocking* (row rejected or batch stopped): header mismatch, field-count mismatch, conversion failures, NULL in a NOT NULL column, duplicate observation key, value domains (status/result/flag lists), `METRIC_DATE ≠ REPORTING_MONTHEND_DATE`, month/year not matching the date, non-month-end dates, application attributes not constant within an application-month.
*Informational* (reported, never block; counts computed from this CSV): 63 completed tests with no result, 30 exempt rows without an exemption level, 123 blank `RFB`, 117 blank `TOTAL_RFB`.

Cross-column rules that were **pre-verified clean on this CSV** but are *not* hard gates (a future real extract may legitimately differ): EON↔GRN↔application name 1:1, cost-centre code↔name, legal-entity code↔name and bank flags, hierarchy parent/child, building→location, M&A flag vs acquired entity.

## Not modelled (and why)

No metric names/families, targets, thresholds, SLAs or severity order exist in the source. Tier, P-codes, ARR codes and RTO bands are kept as neutral labels with **no defined direction**.

## All 57 source columns – types and meaning

| # | Column | Snowflake type | Nullable | Observed nulls | Meaning (from the data dictionary) |
|---|---|---|---|---|---|
| 1 | `METRIC_ID` | VARCHAR(20) | No | 0 | Identifier for the metric definition or measurement group represented by the row. |
| 2 | `METRIC_DATE` | DATE | No | 0 | Effective date on which the metric is measured or reported. |
| 3 | `METRIC_DATE_TYPE` | VARCHAR(20) | No | 0 | Describes the reporting-date convention used for METRIC_DATE. |
| 4 | `IS_NUMERATOR` | NUMBER(1,0) | No | 0 | Indicates whether the row contributes to the numerator of a calculated metric. |
| 5 | `IS_DENOMINATOR` | NUMBER(1,0) | No | 0 | Indicates whether the row contributes to the denominator of a calculated metric. |
| 6 | `EON_ID` | VARCHAR(20) | No | 0 | Synthetic key for the application or technology entity associated with the row. |
| 7 | `BUILDING_NAME` | VARCHAR(50) | No | 0 | Primary synthetic building associated with the application or recorded event. |
| 8 | `EVENT_LOCATION` | VARCHAR(50) | No | 0 | Synthetic geographic or site label where the relevant event or application activity is associated. |
| 9 | `APPLICATION_TIER` | NUMBER(1,0) | No | 0 | Priority or criticality tier assigned to the application. |
| 10 | `EXEMPTION_LEVEL_1` | VARCHAR(50) | Yes | 10,254 | First-level exemption classification when a test or control requirement does not apply normally. |
| 11 | `TEST_STATUS` | VARCHAR(30) | No | 0 | Current state of the test or control assessment. |
| 12 | `TEST_RESULT` | VARCHAR(20) | Yes | 3,888 | Outcome of a completed test. |
| 13 | `SYSTEM_RTC` | NUMBER(1,0) | No | 0 | Indicates whether a system-level remediation, risk, or control condition is active. |
| 14 | `RFB` | NUMBER(10,0) | Yes | 123 | Count of row-level risk findings, remediation items, or related exceptions. |
| 15 | `TOTAL_RFB` | NUMBER(10,0) | Yes | 117 | Total findings or remediation items associated with the relevant grouping. |
| 16 | `COMPLIANCE_STATUS` | VARCHAR(30) | No | 0 | Overall compliance classification for the row. |
| 17 | `COMPLIANCE_REASON` | VARCHAR(60) | No | 0 | Reason supporting the assigned compliance status. |
| 18 | `RTO_CHANGE_DATE` | DATE | Yes | 7,445 | Date on which the application's recovery-time objective was most recently changed. |
| 19 | `GRN` | VARCHAR(100) | No | 0 | Synthetic globally formatted resource name for the application. |
| 20 | `APPLICATION_NAME` | VARCHAR(100) | No | 0 | Human-readable synthetic application name. |
| 21 | `APPLICATION_RTO` | VARCHAR(30) | No | 0 | Recovery-time objective category assigned to the application. |
| 22 | `HAS_CTIRICAL_KBS` | VARCHAR(1) | No | 0 | Indicates whether the application has a critical knowledge-base or business-service designation. |
| 23 | `LIFECYCLE_PHASE` | VARCHAR(30) | No | 0 | Current lifecycle stage of the application. |
| 24 | `ASSET_RISK_RATING_2` | VARCHAR(10) | No | 0 | Synthetic overall asset-risk rating. |
| 25 | `ARR_AVAILABILITY` | VARCHAR(10) | No | 0 | Availability component of the synthetic application risk rating. |
| 26 | `ARR_CONFIDENTIALITY` | VARCHAR(10) | No | 0 | Confidentiality component of the synthetic application risk rating. |
| 27 | `ARR_INTEGRITY` | VARCHAR(10) | No | 0 | Integrity component of the synthetic application risk rating. |
| 28 | `IS_MERGERS_ACQUISITIONS_ASSET` | VARCHAR(1) | No | 0 | Indicates whether the application is associated with a synthetic acquired entity. |
| 29 | `ACQUIRED_ENTITY` | VARCHAR(60) | No | 0 | Synthetic acquired-entity classification or name. |
| 30 | `BU_SUPER_DIVISION` | VARCHAR(100) | No | 0 | Top level of the synthetic business-unit hierarchy. |
| 31 | `BU_DIVISION` | VARCHAR(100) | No | 0 | Division within the synthetic business-unit hierarchy. |
| 32 | `BU_SUPER_DEPARTMENT` | VARCHAR(100) | No | 0 | Super-department within the synthetic business-unit hierarchy. |
| 33 | `BU_DEPARTMENT` | VARCHAR(100) | Yes | 1,271 | Lowest department level in the synthetic business-unit hierarchy. |
| 34 | `ORG_GROUP_TYPE` | VARCHAR(30) | No | 0 | Identifies the organizational hierarchy level applicable to the row. |
| 35 | `SUPER_DIVISION` | VARCHAR(100) | No | 0 | Top level of the second synthetic organizational hierarchy. |
| 36 | `DIVISION` | VARCHAR(100) | No | 0 | Division within the second synthetic organizational hierarchy. |
| 37 | `SUPER_DEPARTMENT` | VARCHAR(100) | No | 0 | Super-department within the second synthetic organizational hierarchy. |
| 38 | `DEPARTMENT` | VARCHAR(100) | Yes | 1,271 | Department within the second synthetic organizational hierarchy. |
| 39 | `BUS_ORG_LG_NM` | VARCHAR(100) | No | 0 | Detailed synthetic business-organization label associated with the hierarchy. |
| 40 | `COST_CENTER_CODE` | VARCHAR(20) | No | 0 | Synthetic accounting or organizational cost-center code. |
| 41 | `COST_CENTER_NAME` | VARCHAR(100) | No | 0 | Human-readable synthetic cost-center name. |
| 42 | `EMPLOYEE_BUILDING_NAME` | VARCHAR(50) | No | 0 | Synthetic building associated with the application owner or responsible employee. |
| 43 | `EMPLOYEE_COUNTRY_NAME` | VARCHAR(50) | No | 0 | Synthetic country associated with the application owner or responsible employee. |
| 44 | `PRIMARY_BUS_FIRST_NAME` | VARCHAR(100) | No | 0 | First name of the fictional primary business owner. |
| 45 | `PRIMARY_BUS_LAST_NAME` | VARCHAR(100) | No | 0 | Last name of the fictional primary business owner. |
| 46 | `PRIMARY_IT_FIRST_NAME` | VARCHAR(100) | No | 0 | First name of the fictional primary technology owner. |
| 47 | `PRIMARY_IT_LAST_NAME` | VARCHAR(100) | No | 0 | Last name of the fictional primary technology owner. |
| 48 | `LEGAL_ENTITY_CODE` | VARCHAR(20) | No | 0 | Synthetic legal-entity code associated with the application. |
| 49 | `LEGAL_ENTITY_NAME` | VARCHAR(100) | No | 0 | Human-readable fictional legal-entity name. |
| 50 | `IS_USBANKS` | VARCHAR(1) | No | 0 | Generic synthetic flag indicating membership in bank grouping A. |
| 51 | `IS_MSBNA` | VARCHAR(1) | No | 0 | Generic synthetic flag indicating membership in bank grouping B. |
| 52 | `IS_MSPBNA` | VARCHAR(1) | No | 0 | Generic synthetic flag indicating membership in bank grouping C. |
| 53 | `USBANKS_LE_LIST` | VARCHAR(50) | Yes | 1,996 | Pipe-delimited list of generic bank groupings applicable to the legal entity. |
| 54 | `KBS_FLAG_FLAG` | VARCHAR(1) | No | 0 | Secondary synthetic critical knowledge-base or business-service flag. |
| 55 | `REPORTING_MONTHEND_DATE` | DATE | No | 0 | Month-end reporting date for the row. |
| 56 | `REPORTING_MONTH` | NUMBER(2,0) | No | 0 | Numeric month derived from REPORTING_MONTHEND_DATE. |
| 57 | `REPORTING_YEAR` | NUMBER(4,0) | No | 0 | Four-digit year derived from REPORTING_MONTHEND_DATE. |

## Source → raw → typed mapping

| # | Column | Source dictionary type | Raw type | Typed/final type | Conversion |
|---|---|---|---|---|---|
| 1 | `METRIC_ID` | String / identifier | VARCHAR | VARCHAR(20) | none (text) |
| 2 | `METRIC_DATE` | Date | VARCHAR | DATE | TRY_TO_DATE(..., 'YYYY-MM-DD') |
| 3 | `METRIC_DATE_TYPE` | Categorical text | VARCHAR | VARCHAR(20) | none (text) |
| 4 | `IS_NUMERATOR` | Integer flag (0/1) | VARCHAR | NUMBER(1,0) | TRY_TO_NUMBER(...) |
| 5 | `IS_DENOMINATOR` | Integer flag (0/1) | VARCHAR | NUMBER(1,0) | TRY_TO_NUMBER(...) |
| 6 | `EON_ID` | String / identifier | VARCHAR | VARCHAR(20) | none (text) |
| 7 | `BUILDING_NAME` | Categorical text | VARCHAR | VARCHAR(50) | none (text) |
| 8 | `EVENT_LOCATION` | Categorical text | VARCHAR | VARCHAR(50) | none (text) |
| 9 | `APPLICATION_TIER` | Integer category | VARCHAR | NUMBER(1,0) | TRY_TO_NUMBER(...) |
| 10 | `EXEMPTION_LEVEL_1` | Categorical text / nullable | VARCHAR | VARCHAR(50) | none (text) |
| 11 | `TEST_STATUS` | Categorical text | VARCHAR | VARCHAR(30) | none (text) |
| 12 | `TEST_RESULT` | Categorical text / nullable | VARCHAR | VARCHAR(20) | none (text) |
| 13 | `SYSTEM_RTC` | Integer flag (0/1) | VARCHAR | NUMBER(1,0) | TRY_TO_NUMBER(...) |
| 14 | `RFB` | Non-negative integer | VARCHAR | NUMBER(10,0) | TRY_TO_NUMBER(...) |
| 15 | `TOTAL_RFB` | Non-negative integer | VARCHAR | NUMBER(10,0) | TRY_TO_NUMBER(...) |
| 16 | `COMPLIANCE_STATUS` | Categorical text | VARCHAR | VARCHAR(30) | none (text) |
| 17 | `COMPLIANCE_REASON` | Categorical text | VARCHAR | VARCHAR(60) | none (text) |
| 18 | `RTO_CHANGE_DATE` | Date / nullable | VARCHAR | DATE | TRY_TO_DATE(..., 'YYYY-MM-DD') |
| 19 | `GRN` | String / identifier | VARCHAR | VARCHAR(100) | none (text) |
| 20 | `APPLICATION_NAME` | Categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 21 | `APPLICATION_RTO` | Ordinal categorical text | VARCHAR | VARCHAR(30) | none (text) |
| 22 | `HAS_CTIRICAL_KBS` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 23 | `LIFECYCLE_PHASE` | Categorical text | VARCHAR | VARCHAR(30) | none (text) |
| 24 | `ASSET_RISK_RATING_2` | Ordinal categorical text | VARCHAR | VARCHAR(10) | none (text) |
| 25 | `ARR_AVAILABILITY` | Ordinal categorical text | VARCHAR | VARCHAR(10) | none (text) |
| 26 | `ARR_CONFIDENTIALITY` | Ordinal categorical text | VARCHAR | VARCHAR(10) | none (text) |
| 27 | `ARR_INTEGRITY` | Ordinal categorical text | VARCHAR | VARCHAR(10) | none (text) |
| 28 | `IS_MERGERS_ACQUISITIONS_ASSET` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 29 | `ACQUIRED_ENTITY` | Categorical text | VARCHAR | VARCHAR(60) | none (text) |
| 30 | `BU_SUPER_DIVISION` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 31 | `BU_DIVISION` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 32 | `BU_SUPER_DEPARTMENT` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 33 | `BU_DEPARTMENT` | Hierarchical categorical text / nullable | VARCHAR | VARCHAR(100) | none (text) |
| 34 | `ORG_GROUP_TYPE` | Categorical text | VARCHAR | VARCHAR(30) | none (text) |
| 35 | `SUPER_DIVISION` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 36 | `DIVISION` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 37 | `SUPER_DEPARTMENT` | Hierarchical categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 38 | `DEPARTMENT` | Hierarchical categorical text / nullable | VARCHAR | VARCHAR(100) | none (text) |
| 39 | `BUS_ORG_LG_NM` | Categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 40 | `COST_CENTER_CODE` | String / identifier | VARCHAR | VARCHAR(20) | none (text) |
| 41 | `COST_CENTER_NAME` | Categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 42 | `EMPLOYEE_BUILDING_NAME` | Categorical text | VARCHAR | VARCHAR(50) | none (text) |
| 43 | `EMPLOYEE_COUNTRY_NAME` | Categorical text | VARCHAR | VARCHAR(50) | none (text) |
| 44 | `PRIMARY_BUS_FIRST_NAME` | Synthetic person name | VARCHAR | VARCHAR(100) | none (text) |
| 45 | `PRIMARY_BUS_LAST_NAME` | Synthetic person name | VARCHAR | VARCHAR(100) | none (text) |
| 46 | `PRIMARY_IT_FIRST_NAME` | Synthetic person name | VARCHAR | VARCHAR(100) | none (text) |
| 47 | `PRIMARY_IT_LAST_NAME` | Synthetic person name | VARCHAR | VARCHAR(100) | none (text) |
| 48 | `LEGAL_ENTITY_CODE` | String / identifier | VARCHAR | VARCHAR(20) | none (text) |
| 49 | `LEGAL_ENTITY_NAME` | Categorical text | VARCHAR | VARCHAR(100) | none (text) |
| 50 | `IS_USBANKS` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 51 | `IS_MSBNA` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 52 | `IS_MSPBNA` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 53 | `USBANKS_LE_LIST` | Delimited categorical text / nullable | VARCHAR | VARCHAR(50) | none (text) |
| 54 | `KBS_FLAG_FLAG` | Y/N text flag | VARCHAR | VARCHAR(1) | none (text) |
| 55 | `REPORTING_MONTHEND_DATE` | Date | VARCHAR | DATE | TRY_TO_DATE(..., 'YYYY-MM-DD') |
| 56 | `REPORTING_MONTH` | Integer | VARCHAR | NUMBER(2,0) | TRY_TO_NUMBER(...) |
| 57 | `REPORTING_YEAR` | Integer | VARCHAR | NUMBER(4,0) | TRY_TO_NUMBER(...) |
