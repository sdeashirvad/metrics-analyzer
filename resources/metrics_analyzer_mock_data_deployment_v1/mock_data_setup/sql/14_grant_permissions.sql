-- =====================================================================================
-- 14_grant_permissions.sql
-- Minimal-privilege read access for ONE role: METRICS_ANALYZER_DEMO_VIEWER. Touches only the MOCK_DATA objects created here.
-- Nothing on METRICS_ANALYZER.DQ is granted. Status: UNEXECUTED. Run as a role that owns the objects (or SECURITYADMIN for the role).
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = '<SETUP_ROLE>';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = '<WAREHOUSE_NAME>';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

-- 14.1 The viewer role (skip if your organisation already has an equivalent role: replace the name everywhere in this file).
CREATE ROLE IF NOT EXISTS METRICS_ANALYZER_DEMO_VIEWER COMMENT = 'Read-only access to METRICS_ANALYZER.MOCK_DATA demo objects and the compliance agent.';

-- 14.2 Container and compute access.
GRANT USAGE ON DATABASE METRICS_ANALYZER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT USAGE ON SCHEMA   METRICS_ANALYZER.MOCK_DATA TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT USAGE ON WAREHOUSE IDENTIFIER($WH_NAME) TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.3 Data the agent reads. Cortex Analyst runs with the caller's rights, so the caller needs SELECT on the semantic view
--      and on the objects behind it.
GRANT SELECT ON TABLE METRICS_ANALYZER.MOCK_DATA.APPLICATION_COMPLIANCE        TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT SELECT ON VIEW  METRICS_ANALYZER.MOCK_DATA.V_APPLICATION_MONTH_STATUS    TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
GRANT SELECT ON SEMANTIC VIEW METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.4 The agent.
GRANT USAGE ON AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- 14.5 Not granted on purpose: raw, staging, audit, rejected-row tables, the stage, and anything in DQ.
--      The viewer cannot see unvalidated data or load history.

-- ---- Optional B: Cortex entitlement. Run ONLY if SHOW GRANTS (in 00_preflight) showed PUBLIC lacks SNOWFLAKE.CORTEX_USER ----
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
-- If your release exposes the agent-specific database role, grant that instead / as well (confirm the name in PERMISSIONS.md):
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- ---- Optional C: let the viewer monitor the agent's threads/traces. Syntax UNVERIFIED: confirm in the docs before use ----
-- GRANT MONITOR ON AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 TO ROLE METRICS_ANALYZER_DEMO_VIEWER;

-- ---- Administrator-only note (NOT a script step) ----
-- If the account's region does not host the model Cortex needs, an ACCOUNTADMIN may have to set CORTEX_ENABLED_CROSS_REGION.
-- This script never changes account parameters. See PERMISSIONS.md.

-- 14.6 Give the role to the people who should use the demo (replace <USER_NAME>; one statement per user).
-- GRANT ROLE METRICS_ANALYZER_DEMO_VIEWER TO USER <USER_NAME>;

-- Checkpoint 14
SHOW GRANTS TO ROLE METRICS_ANALYZER_DEMO_VIEWER;
-- Expected: USAGE on the database, schema, warehouse and agent; SELECT on the table, view and semantic view; nothing on DQ.
