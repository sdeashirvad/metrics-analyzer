-- =====================================================================================
-- 13_create_agent.sql
-- Cortex Agent METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 with one Cortex Analyst tool bound to
-- the semantic view. Status: UNEXECUTED (field names taken from the CREATE AGENT documentation; see AGENT_CONFIGURATION.md).
-- IF NOT EXISTS: re-running does not overwrite. To change a live agent use the ALTER block at the bottom.
-- BEFORE RUNNING: replace <WAREHOUSE_NAME> inside the specification below (it appears once) with a real warehouse name.
-- =====================================================================================
-- Set these two values ONCE per worksheet, then run the whole file.
SET SETUP_ROLE = 'ACCOUNTADMIN';          -- a role that can create objects in METRICS_ANALYZER (from 00_preflight 0.4)
SET WH_NAME    = 'COMPUTE_WH';      -- an existing warehouse (from 00_preflight 0.2)
USE ROLE IDENTIFIER($SETUP_ROLE);
USE WAREHOUSE IDENTIFIER($WH_NAME);
USE DATABASE METRICS_ANALYZER;
USE SCHEMA METRICS_ANALYZER.MOCK_DATA;

CREATE AGENT IF NOT EXISTS METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1
  COMMENT = 'Analyses the synthetic application compliance dataset through the SV_APPLICATION_COMPLIANCE_V1 semantic view.'
  PROFILE = '{"display_name": "Application Compliance Analyst"}'
  FROM SPECIFICATION
  $$
    # Cortex Agent specification for AGENT_APPLICATION_COMPLIANCE_V1 (UNEXECUTED; field names per the CREATE AGENT docs).
    # Replace <WAREHOUSE_NAME> with the warehouse Cortex Analyst should use. Nothing else needs editing.
    models:
      orchestration: auto

    orchestration:
      budget:
        seconds: 60
        tokens: 16000

    instructions:
      response: |
        Be concise and numerate. Lead with the answer, then the supporting figures, then any caveat.
        Always state the reporting period used (a month-end date). If the user gave none, use 2026-10-31 and say so.
        Give counts with their population (for example "300 of 923 applications") so the reader can judge scale.
        Mark any measure that is provisional as "provisional" in the sentence where it appears.
        Never describe a tier, risk code or RTO band as higher, lower, worse or more critical: these codes have no defined direction here.
        Present tables for lists of more than three items. Do not invent business definitions, targets, thresholds or SLAs.
        All names in this dataset are synthetic; never imply they refer to real people or organisations.
      orchestration: |
        Use the analyst tool for every question about this dataset. Do not answer numeric questions from memory.
        Count applications with COUNT(DISTINCT EON_ID) or from the application-month view. Never use COUNT(*) of metric rows as an application count.
        Do not sum TOTAL_RFB across metric rows. It repeats for every metric of the same application and month; use the application-month open findings value.
        SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR) is a provisional rate. Variants A and B are not stored columns. Do not compare that rate across metrics.
        For one month, use that month's attributes. For a roll-up across months, use each application's latest month.
        Observation rows grow from about 700 to about 1,100 by construction. Use shares and rates for trends, not raw row counts.
        If the question needs a definition the model does not hold (metric names, severity, thresholds, regulations), say so and offer what the data can show.
        If "compliance rate" or "percentage" is requested, answer with the provisional rate and its numerator and denominator, labelled provisional.
        If "critical", "high risk" or "worst" is used, ask whether to rank by non-compliant applications, failed tests or open findings instead.
        If a question could mean either organisation hierarchy, use the business organisation hierarchy (super division, division) unless the user says BU or business unit.
        Ask one short clarifying question only when the answer would change materially; otherwise state the assumption and proceed.
      sample_questions:
        - question: "How many applications are non-compliant in the latest month?"
          answer: "Counts distinct applications with at least one Non_Compliant metric row for 2026-10-31."
        - question: "Which super divisions have the most non-compliant applications this month?"
          answer: "Ranks super divisions by non-compliant applications with the share of applications reporting."
        - question: "Which applications became newly non-compliant compared with last month?"
          answer: "Lists applications whose movement status is NEWLY_NON_COMPLIANT (provisional definition)."
        - question: "Show the trend of non-compliant applications over the last 12 months."
          answer: "Monthly count of non-compliant applications and applications reporting."
        - question: "How many applications have no completed test this month?"
          answer: "Counts applications with no Test_Complete row for 2026-10-31."

    tools:
      - tool_spec:
          type: cortex_analyst_text_to_sql
          name: ApplicationComplianceAnalyst
          description: |
            Answers questions about application compliance, testing, findings, organisation, legal entity, owners and monthly
            trends from the synthetic enterprise dataset (1,500 applications, 24 metrics, 12 month-ends 2025-11-30 to 2026-10-31).
            Use for any counting, ranking, trend or comparison question. Application counts come from application-month level
            measures; metric-row counts come from observation-level measures. Several measures are provisional.

    tool_resources:
      ApplicationComplianceAnalyst:
        semantic_view: "METRICS_ANALYZER.MOCK_DATA.SV_APPLICATION_COMPLIANCE_V1"
        execution_environment:
          type: warehouse
          warehouse: "COMPUTE_WH"
          query_timeout: 120
  $$;

-- Checkpoint 13
SHOW AGENTS IN SCHEMA METRICS_ANALYZER.MOCK_DATA;            -- Expected: AGENT_APPLICATION_COMPLIANCE_V1
DESCRIBE AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1;
-- Expected: the specification shows one tool ApplicationComplianceAnalyst and the semantic view name.
-- If CREATE AGENT fails: STOP and capture the error text. Typical causes: Cortex Agents not enabled for the account/region,
-- missing CREATE AGENT privilege on the schema, or a specification field name that differs in your account's release.

-- ---- Upgrade path (do NOT run on first install): replaces the live specification, keeps the object and its grants ----
-- ALTER AGENT METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1 MODIFY LIVE VERSION SET SPECIFICATION =
-- $$ ...complete new specification... $$;
