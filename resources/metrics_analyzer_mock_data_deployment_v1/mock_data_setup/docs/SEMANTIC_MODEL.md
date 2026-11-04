# Semantic model – `SV_APPLICATION_COMPLIANCE_V1`

Native Snowflake semantic view (script 12). UNEXECUTED.

## Structure

| Logical table | Source | Grain | Holds |
|---|---|---|---|
| `app_month` | `V_APPLICATION_MONTH_STATUS` | application × month (PRIMARY KEY `EON_ID, REPORTING_MONTHEND_DATE`) | All 42 application attributes, the date dimensions, application-level metrics |
| `obs` | `APPLICATION_COMPLIANCE` | application × metric × month | Metric/test/compliance dimensions, row-level metrics |

Relationship `obs_to_app_month`: `obs (EON_ID, REPORTING_MONTHEND_DATE)` references `app_month (EON_ID, REPORTING_MONTHEND_DATE)` – many rows to one application-month.

**Why two tables:** "how many applications" and "how many rows" are different questions with different grains. With one flat table, `COUNT(*)` would be mistaken for applications and `TOTAL_RFB` would be summed once per metric row. The split makes the correct count the easy one.

## Counting rules encoded in the model

| Question | Use | Not |
|---|---|---|
| Applications reporting / non-compliant / without a completed test / with a failed test | `app_month.*` metrics | `obs.observation_rows` |
| Newly non-compliant / resolved | `app_month.newly_non_compliant_applications`, `resolved_applications` | derived from row counts |
| Open findings | `app_month.open_findings` **for one month** | `SUM(TOTAL_RFB)` over rows; summing across months |
| Rows by status / reason / metric | `obs.*` metrics | application metrics sliced by `obs` dimensions (fan-out; the instructions tell the model to avoid it) |

## Provisional items (labelled in the model's comments and in the agent's answers)

| Item | Why provisional |
|---|---|
| `provisional_compliance_rate` = Σ`IS_NUMERATOR` / Σ`IS_DENOMINATOR` | The client has not supplied the formula; numerator/denominator logic is a generator assumption. Always shown with its numerator and denominator. |
| `open_findings`, `row_level_findings` | Meaning of `RFB`/`TOTAL_RFB` not defined by the client |
| `movement_status` and its counts | Compares with the immediately preceding **calendar** month only; applications absent then are `NO_PRIOR_MONTH` |
| `system_rtc_rows`, numerator/denominator totals | Meaning not supplied |

## Dimensions that are neutral by design

`application_tier`, `asset_risk_rating`, `arr_*` and `application_rto` carry no ranking. The model is told never to call P1/Tier 1 "highest" and never to sort "most critical first".

## Organisation hierarchies

Hierarchy 2 (`super_division → division → super_department → department`) is the default for "division / department / organisation". The `bu_*` columns are used only when the user says BU/business unit. `department` is blank for 11% of application-months (`org_group_type = SUPER_DEPARTMENT`).

## Verified expected answers (from the CSV, used in script 15)

Latest month 2026-10-31: 923 applications reporting, 300 non-compliant, 293 without a completed test, 132 newly non-compliant, 117 resolved, 1870 open findings (provisional).

## Syntax risk list (what to adjust first if script 12 fails)

1. Clause order / keyword spelling in `CREATE SEMANTIC VIEW` (TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS, COMMENT, AI_SQL_GENERATION, AI_QUESTION_CATEGORIZATION).
2. `PRIMARY KEY (…)` on a view-backed logical table, and the relationship syntax `obs (cols) REFERENCES app_month (cols)`.
3. `WITH SYNONYMS = (…)` before `COMMENT =` on each element.
4. `$$…$$` quoting for `AI_SQL_GENERATION` / `AI_QUESTION_CATEGORIZATION` (fallback: single-quoted strings with `''` escaping).
5. `COUNT(DISTINCT IFF(…))`-style metric expressions (fallback: precompute flag columns in the view and use `COUNT(DISTINCT …)` over a filtered fact).
6. Whether a computed dimension expression (`TRIM(a || ' ' || b)`) is accepted (fallback: add `BUSINESS_OWNER`/`IT_OWNER` columns to the view).

## Upgrading

`CREATE SEMANTIC VIEW IF NOT EXISTS` never overwrites. For changes: create `…_V2`, point a test agent at it, then repoint (`ALTER AGENT … MODIFY LIVE VERSION SET SPECIFICATION`). Do not edit V1 in place once users rely on it.
