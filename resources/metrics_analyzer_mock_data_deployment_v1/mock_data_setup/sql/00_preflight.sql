-- =====================================================================================
-- 00_preflight.sql   READ-ONLY. Creates nothing, changes nothing.
-- Purpose : discover the account facts you must supply before running scripts 01-15.
-- Run as  : the role you intend to use for setup (or any role that can see the objects).
-- Status  : UNEXECUTED. Written from Snowflake documentation, not tested on your account.
-- =====================================================================================

-- 0.1 Who am I, where am I?
SELECT CURRENT_ACCOUNT()  AS account_locator,
       CURRENT_REGION()   AS region,
       CURRENT_USER()     AS user_name,
       CURRENT_ROLE()     AS current_role,
       CURRENT_WAREHOUSE() AS current_warehouse,
       CURRENT_DATABASE() AS current_database,
       CURRENT_SCHEMA()   AS current_schema;

-- 0.2 Which warehouse do I use?  Pick the EXISTING warehouse your team already uses for the DQ agent.
--     Copy its exact name from the "name" column. This is your <WAREHOUSE_NAME>.
SHOW WAREHOUSES;

-- 0.3 Which roles do I hold?  Your <SETUP_ROLE> must be able to create a schema in METRICS_ANALYZER.
SELECT CURRENT_AVAILABLE_ROLES() AS roles_i_can_use;

-- 0.4 Does the target database exist, and who may create schemas in it?
SHOW DATABASES LIKE 'METRICS_ANALYZER';
SHOW GRANTS ON DATABASE METRICS_ANALYZER;
--     Look for a role holding OWNERSHIP, or USAGE plus CREATE SCHEMA. That role is a valid <SETUP_ROLE>.

-- 0.5 Existing schemas. DQ must be present and is NEVER touched by this package.
SHOW SCHEMAS IN DATABASE METRICS_ANALYZER;
--     Expected: DQ is listed. MOCK_DATA should NOT be listed yet (script 01 creates it).
--     If MOCK_DATA already exists, stop and read the README troubleshooting section before continuing.

-- 0.6 Existing DQ objects, listed only so you can confirm they are not in scope. Read-only.
SHOW STAGES IN SCHEMA METRICS_ANALYZER.DQ;
SHOW FILE FORMATS IN SCHEMA METRICS_ANALYZER.DQ;
SHOW AGENTS IN SCHEMA METRICS_ANALYZER.DQ;

-- 0.7 Viewer role used in script 14.
SHOW ROLES LIKE 'METRICS_ANALYZER_DEMO_VIEWER';
--     Expected: one row. If none, ask your administrator; this package does not create roles.

-- 0.8 Cortex availability and cross-region inference.
--     Cortex Analyst / Agents run models that may live in another region.
--     Account parameter CORTEX_ENABLED_CROSS_REGION controls whether the account may call them.
SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;
--     Value 'DISABLED' (or empty) and your region does not host the models  ->  see the
--     CONDITIONAL ADMINISTRATOR STEP in PERMISSIONS.md. Do NOT change it from this package.

-- 0.9 Cortex database roles. SNOWFLAKE.CORTEX_USER is granted to PUBLIC by default.
SHOW DATABASE ROLES IN DATABASE SNOWFLAKE;
SHOW GRANTS OF DATABASE ROLE SNOWFLAKE.CORTEX_USER;
SHOW GRANTS OF DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER;
--     If PUBLIC appears under CORTEX_USER, the viewer role already has Cortex access and script 14
--     section B can be skipped. If not, script 14 section B grants CORTEX_AGENT_USER to the viewer role.

-- 0.10 Can my role create the objects? Run each as the setup role; every row should show your role as grantee.
SET CURRENT_ROLE_NAME = CURRENT_ROLE();
SHOW GRANTS TO ROLE IDENTIFIER($CURRENT_ROLE_NAME);
--     Needed in MOCK_DATA after script 01: ownership of the schema covers CREATE TABLE/VIEW/STAGE/
--     FILE FORMAT/SEMANTIC VIEW/AGENT because the creating role owns the schema it creates.
--     Needed before script 01: CREATE SCHEMA on METRICS_ANALYZER.

-- 0.11 Stop here. Write down:  <SETUP_ROLE>, <WAREHOUSE_NAME>, region, cross-region value, CORTEX_USER grantees.
