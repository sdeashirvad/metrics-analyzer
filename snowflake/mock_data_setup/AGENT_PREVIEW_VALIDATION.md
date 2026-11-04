# Agent preview validation

Run on 2026-11-03. No secrets are recorded here. `METRICS_ANALYZER.DQ`, both MCP servers, the loaded batch, and `AGENT_APPLICATION_COMPLIANCE_V1` were not modified. No second semantic view was created. No commit.

## Objects

| Object | Role |
|---|---|
| `METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1` | Agent 1, analysis. Created 2026-11-03 14:38:42 -0800. Left as deployed. |
| `METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_TEXT_TO_SQL_V1` | Agent 2, text-to-SQL. Created 2026-11-03 15:03:53 -0800 by `sql/18_create_text_to_sql_agent.sql`. |
| `METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1` | Semantic view used by both agents. Not altered for Agent 2. |

Agent 1 has one Cortex Analyst tool, `ApplicationComplianceAnalyst`, warehouse `COMPUTE_WH`, timeout 120 seconds. Its instructions still count applications from the application-month grain, refuse to sum `TOTAL_RFB` across metric rows, and keep the two organisation trees apart.

Agent 2 has one Cortex Analyst tool, `ApplicationComplianceSql`, on the same semantic view and warehouse. It has no other configured tool. Its instructions tell it to paste the executed SQL and the tool result, to stay read-only, and to follow the same grain and hierarchy rules. The semantic view already supports both grains: `app_month` is one row per `EON_ID` and reporting month (9,784 rows, verified), and `obs` is `APPLICATION_COMPLIANCE` at `EON_ID + METRIC_ID + METRIC_DATE`.

## Identities

There is no Snowflake user named `DEMO_VIEWER`.

The existing role is `METRICS_ANALYZER_DEMO_VIEWER`, owned by `ACCOUNTADMIN`. It is granted only to user `METRICS_ANALYZER_VIEWER` (login `METRICS-ANALYZER-VIEWER`, default role `METRICS_ANALYZER_DEMO_VIEWER`). That assignment already existed and was not changed. A temporary grant to the setup user was used to assume the role for the API test and was revoked. `SHOW GRANTS OF ROLE` afterwards lists only `METRICS_ANALYZER_VIEWER`.

## Grants completed

`sql/19_grant_demo_viewer.sql` added, for `METRICS_ANALYZER_DEMO_VIEWER` only:

- `USAGE` on schema `METRICS_ANALYZER.MOCK_DATA` (database `USAGE` and warehouse `COMPUTE_WH` `USAGE` were already present)
- `SELECT` on `APPLICATION_COMPLIANCE`
- `SELECT` on `V_APPLICATION_MONTH_STATUS`
- `SELECT` on semantic view `SV_APPLICATION_COMPLIANCE_V1`
- `USAGE` on `AGENT_APPLICATION_COMPLIANCE_V1`
- `USAGE` on `AGENT_APPLICATION_TEXT_TO_SQL_V1`

`SNOWFLAKE.CORTEX_AGENT_USER` was already granted to the role. `SNOWFLAKE.CORTEX_USER` was not granted again; `PUBLIC` already has it. `MONITOR` was not granted. No account privilege `READ UNREDACTED AI OBSERVABILITY EVENTS TABLE` is on this role. The role's existing DQ grants were left as they were. With secondary roles disabled, `SELECT` on `RAW_APPLICATION_COMPLIANCE` fails with `002003`.

No grants are pending. `DEMO_VIEWER_GRANTS_PENDING.sql` was not created.

## How SQL and rows are exposed

`SNOWFLAKE.CORTEX.DATA_AGENT_RUN` returns the executed statement and the dataset on the tool result, not only in the assistant sentence:

- `content[].tool_result` where `type` is `system_execute_sql`
- `json.sql` is the statement Snowflake ran
- `json.result_set.data` is the cell values
- `json.result_set.resultSetMetaData.rowType[].name` is the column names
- `json.result_set.resultSetMetaData.numRows` is the row count
- `json.query_id` is the query id

Agent 2's reply text also copied that SQL and those rows for every data question in this run. The tool result is the source to trust. A sentence that restates numbers is not, by itself, the executed dataset. The current backend parser keeps only assistant text and drops this tool result, so a backend call through that parser would not reliably return the dataset.

## Invocation contract

Send the envelope as the user message text. `DATA_AGENT_RUN` has no separate context argument.

Register row:

```json
{
  "entry_surface": "register_row",
  "eon_id": "<selected EON_ID>",
  "metric_id": "<selected METRIC_ID, or null>",
  "reporting_monthend_date": "<selected date, or null>",
  "active_filters": {},
  "user_question": "<user's question>"
}
```

General section:

```json
{
  "entry_surface": "general",
  "eon_id": null,
  "metric_id": null,
  "reporting_monthend_date": null,
  "active_filters": {},
  "user_question": "<user's question>"
}
```

Agent 2 kept the supplied `EON610516` / `M384010` / `2026-10-31` and did not substitute another application. A null identifier that the question needs should produce a question back, not a guessed value. A general message with no application is a portfolio question. If no month is supplied, Agent 2 is instructed to use `2026-10-31` and say so.

## API test as the viewer role

Snowsight was not opened. The test called `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` in a session whose `CURRENT_ROLE()` was `METRICS_ANALYZER_DEMO_VIEWER` and whose secondary roles were empty. That is the same agent runtime the preview uses. It is not a click-through of the Snowsight playground.

Independent SQL in that same session:

- 923 applications reporting and 300 non-compliant on 2026-10-31
- BU super divisions: 82/233, 77/257, 52/162, 38/130, 27/77, 24/64
- Business-organisation super divisions: 65/194, 50/137, 48/144, 37/128, 36/111, 33/105, 21/58, 10/46
- Test status rows: Test_Complete 736, No_Test 168, Test_Pending 109, Exempt 83
- `EON610516` / `M384010` / 2026-10-31: Pending, Test_Pending
- Monthly series from 197/596 through 300/923, twelve months

Agent 1 tool results matched those figures for the portfolio (923 and 300), all six BU groups, and both metric rows for `EON610516` (`M384010` and `M385554`, both Pending / Test_Pending). Its reply is an explanation and does not include the SQL. The SQL is still on the tool result.

Agent 2 tool results:

| Call | Rows | Match |
|---|---|---|
| Distinct applications on 2026-10-31 | 1, value 923 | Yes |
| Non-compliant by business-organisation super division | 8 | Counts match the independent query |
| Test-status distribution | 4 | 736, 168, 109, 83 |
| Metric row `EON610516` / `M384010` | 1 | Pending, Test_Pending |
| Monthly trend | 12 | Counts match; share denominator is applications reporting that month |
| Register-row envelope | 1 | Same application, metric, and date |
| Delete rows for `EON610516` | no query | Refused. No `system_execute_sql` tool call |

The detail query included `LIMIT 100` and returned 1 row, so it was not truncated. None of the aggregate results were limited below the independent row counts. Full text, SQL, and cells are in `export/agent_preview_results.json`.

## Snowsight steps still available

1. Sign in as `METRICS_ANALYZER_VIEWER`.
2. Set the role to `METRICS_ANALYZER_DEMO_VIEWER` and the warehouse to `COMPUTE_WH`.
3. Open AI & ML, Agents, `AGENT_APPLICATION_COMPLIANCE_V1`, Playground. Ask for the 2026-10-31 portfolio summary and the BU super-division breakdown.
4. Open `AGENT_APPLICATION_TEXT_TO_SQL_V1`. Ask "Count distinct applications reporting on 2026-10-31." Confirm the playground shows the SQL and a one-row result of 923.
5. Paste the register-row JSON above and confirm the row stays on `EON610516` and `M384010`.

## Backend

The two agents are separate objects and can be invoked independently by name. The current application parser will not surface Agent 2's executed SQL or `result_set` until it reads the `system_execute_sql` tool result. No application code was changed.
