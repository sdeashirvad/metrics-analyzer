# Permissions

All grants are in `sql/14_grant_permissions.sql` and are UNEXECUTED. The principle is **one viewer role, read-only, MOCK_DATA only**.

## Roles

| Role | Used for | Needs |
|---|---|---|
| `<SETUP_ROLE>` (yours) | Scripts 01–15 | Create schema in `METRICS_ANALYZER` (OWNERSHIP, or USAGE + CREATE SCHEMA); then it owns everything it creates. CREATE TABLE/VIEW/STAGE/FILE FORMAT/SEMANTIC VIEW/AGENT in `MOCK_DATA` come from owning the schema. USAGE on the warehouse. |
| `METRICS_ANALYZER_DEMO_VIEWER` (created by script 14) | People who query or chat with the agent | See below. |

## Viewer role grants

| Object | Privilege | Why |
|---|---|---|
| Database `METRICS_ANALYZER` | USAGE | resolve names |
| Schema `MOCK_DATA` | USAGE | resolve names |
| Warehouse (your choice) | USAGE | run the generated SQL |
| `APPLICATION_COMPLIANCE`, `V_APPLICATION_MONTH_STATUS` | SELECT | Cortex Analyst runs the generated SQL as the caller |
| `SV_APPLICATION_COMPLIANCE_V1` | SELECT | query the semantic view |
| `AGENT_APPLICATION_COMPLIANCE_V1` | USAGE | chat with the agent |

**Deliberately not granted:** raw, staging, audit and rejected-row tables; the stage; anything in `DQ`; any account-level privilege.

## Cortex entitlement (account specific – check, do not assume)

- Preflight sections 0.8 and 0.9 show whether `PUBLIC` already holds `SNOWFLAKE.CORTEX_USER`. If it does, no extra grant is needed.
- If not, script 14 Optional B grants `SNOWFLAKE.CORTEX_USER` (and, where your release exposes it, `SNOWFLAKE.CORTEX_AGENT_USER`) to the viewer role. **Confirm the exact database-role names in your account** (`SHOW DATABASE ROLES IN DATABASE SNOWFLAKE;`) before running – this package could not verify them.
- If the region does not host the model Cortex needs, an `ACCOUNTADMIN` may need to enable cross-region inference (`CORTEX_ENABLED_CROSS_REGION`). **That is an account-wide setting with data-residency consequences; this package never changes it.** Raise it with your administrator only if the agent reports a model/region error.

## Unverified items

| Item | Status |
|---|---|
| `GRANT SELECT ON SEMANTIC VIEW …` | Per documentation; if rejected try `GRANT REFERENCES` and `GRANT SELECT` as the error indicates |
| `GRANT USAGE ON AGENT …` | Per documentation |
| `GRANT MONITOR ON AGENT …` | Syntax unverified; left commented out |
| Whether the viewer needs `CREATE THREAD`/similar for chat history | Unknown; capture any privilege error from the Playground |

## Verifying as the viewer

```sql
USE ROLE METRICS_ANALYZER_DEMO_VIEWER;
USE WAREHOUSE <WAREHOUSE_NAME>;
SELECT COUNT(*) FROM METRICS_ANALYZER.MOCK_DATA.APPLICATION_COMPLIANCE;        -- 11399
SELECT COUNT(*) FROM METRICS_ANALYZER.MOCK_DATA.RAW_APPLICATION_COMPLIANCE;    -- must FAIL (no privilege)
```
