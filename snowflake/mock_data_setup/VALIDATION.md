# MOCK_DATA validation note

Executed on 2026-11-03 as `SDEASHIRVAD` with role `ACCOUNTADMIN` and warehouse `COMPUTE_WH`. That role is the explicit override for this run. Script `14_grant_permissions.sql` was not executed, so `METRICS_ANALYZER_DEMO_VIEWER` was not created. Nothing in `METRICS_ANALYZER.DQ` was altered. `METRICS_ANALYZER.MOCK_DATA.CURSOR_DEV_MCP` and `METRICS_ANALYZER.DQ.METRICS_ANALYZER_CURSOR_READ_MCP` were left in place. No git commit.

## Files inspected

Authoritative file: `resources/metrics_analyzer_mock_data_deployment_v1/mock_data_setup/data/synthetic_enterprise_data.csv`.

- SHA-256 `08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3`
- 6,701,793 bytes
- 11,400 lines (header + 11,399 data rows), 57 columns
- Batch `MOCK_V1_20261103`, dataset version `v1-seed20261103`
- The XLSX and ZIP were not loaded

Staged with `PUT ... AUTO_COMPRESS=FALSE OVERWRITE=TRUE`. `LIST` showed `synthetic_enterprise_data.csv` at 6,701,793 bytes.

## What executed

Scripts `01` through `13`, `15`, and `16` ran against `METRICS_ANALYZER.MOCK_DATA`. Script `00` was not used as a stop check because the empty `MOCK_DATA` schema already existed. Script `14` did not run. Script `17` is the read-only shape of the local export; the export itself is `export/export_local_json.py`.

Two package statements were changed before they could succeed:

1. `BANK_LIST_VS_FLAGS` in `07_validate_staging.sql`. Snowflake `CONCAT_WS` returns NULL when any argument is NULL, so a mixed Y/N row never matched `USBANKS_LE_LIST`. The check now uses `ARRAY_CONSTRUCT_COMPACT` and `ARRAY_TO_STRING`, which drops the N flags the way the generator does. Before that change the rule rejected 9,403 rows and promotion inserted nothing. After it, rejected rows are 0.
2. `SV_APPLICATION_COMPLIANCE_V1` does not declare `app_month.open_findings_value` as a fact. Snowflake rejected that fact because `OPEN_FINDINGS` on the view is already `MAX(TOTAL_RFB)`. The metric `app_month.open_findings` is `SUM(app_month.OPEN_FINDINGS)`.

`SHOW SEMANTIC DIMENSIONS IN SEMANTIC VIEW` is not valid in this account. The checkpoint lines now omit the extra `VIEW` keyword. The semantic view itself was created before that checkpoint failed.

## Reconciliation

| Check | Result |
|---|---|
| Raw / staging / final | 11399 / 11399 / 11399 |
| Conversion errors | 0 |
| Rejected rows | 0 |
| Duplicate grain `EON_ID + METRIC_ID + METRIC_DATE` | 0 |
| Distinct applications | 1500 |
| Distinct metrics | 24 |
| Month span | 2025-11-30 to 2026-10-31 |
| Audit status | `RECONCILED` |
| Minimum `SOURCE_FILE_ROW_NUMBER` | 1 (header was not loaded; 11,399 distinct file-row numbers) |

Per-month final row counts all passed: 699, 763, 827, 859, 908, 943, 978, 1046, 1068, 1117, 1095, 1096.

`V_APPLICATION_MONTH_STATUS`: 9,784 application-months, 1,500 applications, 0 duplicate application-months. October 2026-10-31: 923 reporting, 300 non-compliant, 132 newly non-compliant, 117 resolved, 293 with no completed test, 1,870 open findings, 1,096 metric rows.

Monthly non-compliant and reporting counts match the golden-question series exactly, from 197 / 596 in November 2025 through 300 / 923 in October 2026.

## Objects in MOCK_DATA

Tables: `RAW_APPLICATION_COMPLIANCE`, `STG_APPLICATION_COMPLIANCE`, `APPLICATION_COMPLIANCE`, `DATASET_LOAD_AUDIT`, `DATASET_REJECTED_ROWS`, `APP_PORTFOLIO_MONTHLY_SNAPSHOT`.

Views: `V_STG_ROW_VALIDATION`, `V_STG_VALIDATION_RESULTS`, `V_APPLICATION_MONTH_STATUS`, `V_ORGANIZATION_MONTHLY_SUMMARY`.

Also present: file formats `CLIENT_CSV_FORMAT` and `CLIENT_CSV_FORMAT_NOHEADER`, stage `CLIENT_DATA_STAGE`, semantic view `SV_APPLICATION_COMPLIANCE_V1`, agent `AGENT_APPLICATION_COMPLIANCE_V1`.

The semantic view has logical tables `APP_MONTH` (`V_APPLICATION_MONTH_STATUS`) and `OBS` (`APPLICATION_COMPLIANCE`), relationship on `(EON_ID, REPORTING_MONTHEND_DATE)`. Facts are the row-level numerator, denominator, RFB, and `SYSTEM_RTC` flags, each marked provisional. The agent has one Cortex Analyst tool, `ApplicationComplianceAnalyst`, warehouse `COMPUTE_WH`, query timeout 120 seconds. Instructions tell it to count applications from the application-month grain, not to sum `TOTAL_RFB` across metric rows, to label the numerator/denominator rate provisional, to use one month's attributes for that month and the latest month for a cross-month roll-up, and to treat the growth from about 700 to about 1,100 rows as constructed coverage.

`APP_PORTFOLIO_MONTHLY_SNAPSHOT` has 12 rows for `v1-seed20261103`. October: 923 reporting, 300 non-compliant, 132 newly non-compliant, 117 resolved, 1,096 metric rows, 1,870 open findings. It stores counts and those sums only. `SOURCE_VIEW` is `V_APPLICATION_MONTH_STATUS` and `SOURCE_ROW_COUNT` is 9,784.

`V_ORGANIZATION_MONTHLY_SUMMARY` is a view with `HIERARCHY_NAME` of `BUSINESS_ORG` or `BU`. October contributes 2,755 business-organisation rows and 1,201 BU rows. Each tree's application-months sum to 9,784. The trees are not joined.

## Smoke tests

Script 15 matched the package expectations:

- 2026-10-31 applications: 923 reporting, 300 non-compliant, 293 without a completed test
- Movement: 132 newly non-compliant, 117 resolved
- Open findings: 1870
- Metric rows: 1096, failed tests 273, passed tests 459, numerator 463, denominator 873, provisional rate 0.530355
- Top super divisions and compliance-status counts match G03 and G08
- Semantic view versus base objects: PASS for non-compliant applications, observation rows, and failed-test rows

## Agent answers

Eight questions were sent to `AGENT_APPLICATION_COMPLIANCE_V1` with `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`. Text answers are in `export/agent_golden_answers.json`.

| Question | Agent figure | Independent SQL |
|---|---|---|
| G01 applications reporting | 923 | 923 |
| G02 non-compliant | 300 of 923 | 300 of 923 |
| G03 top super divisions | 65/194, 50/137, and 37/128, matching the expected rows for Super_Division_04, 02, and 06 | Full top 6 also confirmed by smoke test 15.5 |
| G05 no completed test | 293 of 923 | 293 |
| G06 monthly trend | 197/596, peak 312/962 in August 2026, 278 in September, 300/923 in October | Exact series in the snapshot |
| G07 failed completed tests | 273 metric rows | 273 failed, 459 passed |
| G08 status distribution | 463, 324, 183, 126 of 1,096 | Same |
| G10 open findings | 1,870, labelled provisional, one month only | 1870 |

G03's saved answer names the first, second, and lowest-share rows of the top six and the size range 105 to 194. It does not print Super_Division_05, Super_Division_08, or Super_Division_03 as its own lines. The semantic-view query does: 48/144, 36/111, and 33/105.

G07 also said 736 completed tests, 4 of them without a Pass or Fail result, and 247 applications with a failed test. 273 + 459 + 4 = 736. Those extra counts were not in the golden-question table; the failed-row count matches.

## Local export

`export/export_local_json.py` wrote overview (1), monthly trends (12), testing (12), risk distribution by `ASSET_RISK_RATING_2` (4 codes, counts only), organisation contribution (345), application register (923), and metric rows for the first non-compliant `EON_ID` in October (2 rows).

## Provisional items

Movement status compares only the immediately previous calendar month. Open findings are `TOTAL_RFB` taken once per application-month, then summed across applications for that month only. `SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR)` is a provisional rate; variants A and B are not columns. Tier and P/A/C/I codes are not ranked. Application attributes can change across months. Absolute row counts rise by construction, so trends should use shares.

## Not done

No viewer-role grants. No change to the DQ agent. No backend, frontend, Docker, or Nginx change. No commit.

## Agent 2 and demo access

The load section above is unchanged. Viewer grants and the second agent were added afterward. See `AGENT_PREVIEW_VALIDATION.md`.
