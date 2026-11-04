# Agent configuration – `AGENT_APPLICATION_COMPLIANCE_V1`

Created by script 13 from `agent/agent_specification.yaml`. UNEXECUTED; field names were taken from the `CREATE AGENT` documentation and could not be tested on your account.

| Setting | Value |
|---|---|
| Display name | Application Compliance Analyst |
| Model | `orchestration: auto` (Snowflake selects; no model name is hard-coded) |
| Budget | 60 s, 16,000 tokens (adjust if answers are cut off) |
| Tool | one `cortex_analyst_text_to_sql` tool named `ApplicationComplianceAnalyst` |
| Semantic view | `METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1` |
| Execution | warehouse `<WAREHOUSE_NAME>` (**replace once in script 13**), 120 s query timeout |
| Not included | Cortex Search, custom/stored-procedure tools, web access, data-to-chart tools |

## Behaviour rules (full text in `agent/agent_instructions.md`)

1. Always use the analyst tool for numbers; never answer from memory.
2. State the reporting month used; default 2026-10-31 and say so.
3. Show populations next to counts.
4. Label provisional measures; show numerator and denominator with the compliance rate.
5. Never rank tier / risk codes / RTO bands; ask for a defined alternative for "critical" or "worst".
6. Default to hierarchy 2; use BU columns only when asked.
7. Refuse real-world, regulatory, forecast and target/threshold questions.

## Testing

Playground questions and expected answers: `agent/golden_questions.md` (15 questions; expected values computed from the CSV). Acceptance criteria: numeric answers match exactly; the three behavioural checks in script 15 section 15.9 pass.

## Changing the agent

Edit `agent/agent_specification.yaml`, then:
```sql
ALTER AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 MODIFY LIVE VERSION SET SPECIFICATION = $$ <whole yaml> $$;
```
(syntax per documentation, unverified). Keep the yaml and the SQL in step; the yaml in this package is the source of truth.

## Known limits

- It can answer only what the semantic view holds: no metric names, targets, root causes.
- Graphs/markup: a plain Cortex Agent returns text and tables; charts require a front end (the proposed application) or a chart tool, which is intentionally not configured here.
- Chat history, feedback and monitoring features depend on your Snowflake release and role grants (see PERMISSIONS.md).
