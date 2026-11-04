# Golden questions – Application Compliance agent

Expected answers are computed from `synthetic_enterprise_data.csv` (SHA-256 `08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3`). The SQL was run in a local SQLite emulation of `APPLICATION_COMPLIANCE` and `V_APPLICATION_MONTH_STATUS`; it is written in the common subset of SQLite and Snowflake SQL, but **has not been run in Snowflake**. Items marked **PROVISIONAL** depend on definitions the client has not supplied: the agent must say so.

Latest month = 2026-10-31. Compare the agent's numbers with the expected values exactly.

## G01. How many applications reported in the latest month (2026-10-31)?

*Note:* Counts applications once (not metric rows).

```sql
SELECT COUNT(DISTINCT EON_ID) AS applications_reporting FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| applications_reporting |
|---|
| 923 |

## G02. How many applications are non-compliant in the latest month?

*Note:* Non-compliant = at least one Non_Compliant metric row in the month.

```sql
SELECT SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| non_compliant_applications | applications_reporting |
|---|---|
| 300 | 923 |

## G03. Which super divisions have the most non-compliant applications in the latest month? Show the top 6 with the share of their applications.

*Note:* Business organisation hierarchy (not BU). Ties broken by name.

```sql
SELECT SUPER_DIVISION, SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting, ROUND(1.0*SUM(IS_NON_COMPLIANT_APP)/COUNT(*),3) AS share FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31' GROUP BY SUPER_DIVISION ORDER BY non_compliant_applications DESC, SUPER_DIVISION LIMIT 6;
```

Expected:

| SUPER_DIVISION | non_compliant_applications | applications_reporting | share |
|---|---|---|---|
| Super_Division_04 | 65 | 194 | 0.335 |
| Super_Division_02 | 50 | 137 | 0.365 |
| Super_Division_05 | 48 | 144 | 0.333 |
| Super_Division_06 | 37 | 128 | 0.289 |
| Super_Division_08 | 36 | 111 | 0.324 |
| Super_Division_03 | 33 | 105 | 0.314 |

## G04. How many applications became newly non-compliant and how many were resolved compared with the previous month?  — PROVISIONAL

*Note:* PROVISIONAL movement definition: immediately preceding calendar month only; applications not reporting then are NO_PRIOR_MONTH.

```sql
SELECT SUM(CASE WHEN MOVEMENT_STATUS='NEWLY_NON_COMPLIANT' THEN 1 ELSE 0 END) AS newly_non_compliant, SUM(CASE WHEN MOVEMENT_STATUS='RESOLVED' THEN 1 ELSE 0 END) AS resolved FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| newly_non_compliant | resolved |
|---|---|
| 132 | 117 |

## G05. How many applications have no completed test in the latest month?

*Note:* No Test_Complete row for the application in the month.

```sql
SELECT SUM(HAS_NO_COMPLETED_TEST) AS applications_without_completed_test FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| applications_without_completed_test |
|---|
| 293 |

## G06. Show the monthly trend of non-compliant applications and applications reporting.

*Note:* Reporting population varies by month (not every application reports every month): show both columns.

```sql
SELECT REPORTING_MONTHEND_DATE, SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting FROM V_APPLICATION_MONTH_STATUS GROUP BY REPORTING_MONTHEND_DATE ORDER BY REPORTING_MONTHEND_DATE;
```

Expected:

| REPORTING_MONTHEND_DATE | non_compliant_applications | applications_reporting |
|---|---|---|
| 2025-11-30 | 197 | 596 |
| 2025-12-31 | 206 | 652 |
| 2026-01-31 | 234 | 708 |
| 2026-02-28 | 247 | 745 |
| 2026-03-31 | 264 | 780 |
| 2026-04-30 | 272 | 814 |
| 2026-05-31 | 290 | 842 |
| 2026-06-30 | 282 | 903 |
| 2026-07-31 | 294 | 922 |
| 2026-08-31 | 312 | 962 |
| 2026-09-30 | 278 | 937 |
| 2026-10-31 | 300 | 923 |

## G07. How many completed tests failed in the latest month?

*Note:* Metric-row level (a row is a test of one metric for one application).

```sql
SELECT SUM(CASE WHEN TEST_STATUS='Test_Complete' AND TEST_RESULT='Fail' THEN 1 ELSE 0 END) AS failed_test_rows, SUM(CASE WHEN TEST_STATUS='Test_Complete' AND TEST_RESULT='Pass' THEN 1 ELSE 0 END) AS passed_test_rows FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| failed_test_rows | passed_test_rows |
|---|---|
| 273 | 459 |

## G08. What is the distribution of compliance status across metric rows in the latest month?

*Note:* Rows, not applications.

```sql
SELECT COMPLIANCE_STATUS, COUNT(*) AS observation_rows FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31' GROUP BY COMPLIANCE_STATUS ORDER BY observation_rows DESC;
```

Expected:

| COMPLIANCE_STATUS | observation_rows |
|---|---|
| Compliant | 463 |
| Non_Compliant | 324 |
| Pending | 183 |
| Not_Applicable | 126 |

## G09. What is the compliance rate in the latest month?  — PROVISIONAL

*Note:* PROVISIONAL: not a confirmed client metric. The agent must label it provisional and show numerator and denominator.

```sql
SELECT SUM(IS_NUMERATOR) AS numerator_total, SUM(IS_DENOMINATOR) AS denominator_total, ROUND(1.0*SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR),4) AS provisional_compliance_rate FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| numerator_total | denominator_total | provisional_compliance_rate |
|---|---|---|
| 463 | 873 | 0.5304 |

## G10. What are the open findings in the latest month?  — PROVISIONAL

*Note:* PROVISIONAL: TOTAL_RFB taken once per application-month; single month only. Summing TOTAL_RFB over metric rows would overstate it.

```sql
SELECT SUM(OPEN_FINDINGS) AS open_findings FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31';
```

Expected:

| open_findings |
|---|
| 1870.0 |

## G11. What are the top 5 compliance reasons among non-compliant metric rows in the latest month?

*Note:* Ties broken by name.

```sql
SELECT COMPLIANCE_REASON, COUNT(*) AS non_compliant_rows FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31' AND COMPLIANCE_STATUS='Non_Compliant' GROUP BY COMPLIANCE_REASON ORDER BY non_compliant_rows DESC, COMPLIANCE_REASON LIMIT 5;
```

Expected:

| COMPLIANCE_REASON | non_compliant_rows |
|---|---|
| Test_Failed | 117 |
| Open_Findings_Outstanding | 85 |
| Remediation_Overdue | 52 |
| No_Test_Performed | 37 |
| Test_Overdue | 26 |

## G12. Which legal entities have the most non-compliant applications in the latest month? Top 5.

*Note:* Legal entity attributes are per application-month.

```sql
SELECT LEGAL_ENTITY_NAME, SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31' GROUP BY LEGAL_ENTITY_NAME ORDER BY non_compliant_applications DESC, LEGAL_ENTITY_NAME LIMIT 5;
```

Expected:

| LEGAL_ENTITY_NAME | non_compliant_applications | applications_reporting |
|---|---|---|
| Legal_Entity_34 | 18 | 46 |
| Legal_Entity_20 | 15 | 34 |
| Legal_Entity_22 | 15 | 27 |
| Legal_Entity_38 | 15 | 46 |
| Legal_Entity_39 | 15 | 32 |

## G13. Which metrics have the most non-compliant rows in the latest month? Top 5.

*Note:* Metric names are not supplied: report the id only.

```sql
SELECT METRIC_ID, COUNT(*) AS non_compliant_rows FROM APPLICATION_COMPLIANCE WHERE REPORTING_MONTHEND_DATE = '2026-10-31' AND COMPLIANCE_STATUS='Non_Compliant' GROUP BY METRIC_ID ORDER BY non_compliant_rows DESC, METRIC_ID LIMIT 5;
```

Expected:

| METRIC_ID | non_compliant_rows |
|---|---|
| M340202 | 50 |
| M384010 | 36 |
| M346318 | 30 |
| M325402 | 28 |
| M314650 | 20 |

## G14. How many non-compliant applications are there by lifecycle phase in the latest month, with the share of each phase?

*Note:* Small groups: always show the population.

```sql
SELECT LIFECYCLE_PHASE, SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting, ROUND(1.0*SUM(IS_NON_COMPLIANT_APP)/COUNT(*),3) AS share FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31' GROUP BY LIFECYCLE_PHASE ORDER BY non_compliant_applications DESC, LIFECYCLE_PHASE;
```

Expected:

| LIFECYCLE_PHASE | non_compliant_applications | applications_reporting | share |
|---|---|---|---|
| Production | 172 | 555 | 0.31 |
| Retirement | 36 | 114 | 0.316 |
| Development | 33 | 98 | 0.337 |
| Implementation | 32 | 77 | 0.416 |
| Planning | 27 | 79 | 0.342 |

## G15. Which BU super divisions have the most non-compliant applications in the latest month? Top 5.

*Note:* Uses the BU hierarchy because the question says BU.

```sql
SELECT BU_SUPER_DIVISION, SUM(IS_NON_COMPLIANT_APP) AS non_compliant_applications, COUNT(*) AS applications_reporting FROM V_APPLICATION_MONTH_STATUS WHERE REPORTING_MONTHEND_DATE = '2026-10-31' GROUP BY BU_SUPER_DIVISION ORDER BY non_compliant_applications DESC, BU_SUPER_DIVISION LIMIT 5;
```

Expected:

| BU_SUPER_DIVISION | non_compliant_applications | applications_reporting |
|---|---|---|
| BU_Super_Division_05 | 82 | 233 |
| BU_Super_Division_01 | 77 | 257 |
| BU_Super_Division_03 | 52 | 162 |
| BU_Super_Division_04 | 38 | 130 |
| BU_Super_Division_02 | 27 | 77 |

## Behavioural checks (no numeric answer)

| # | Ask | Correct behaviour |
|---|---|---|
| B1 | "What is the compliance rate?" | Gives the provisional rate (0.5304 for 2026-10-31 = 463 / 873), says it is provisional, shows numerator and denominator. |
| B2 | "Which applications are the most critical?" | Does not rank by tier or risk code. Explains no severity direction is defined and offers non-compliant applications, failed tests or open findings instead. |
| B3 | "How many applications are non-compliant?" (no month) | Uses 2026-10-31, says so, answers 300 of 923. |
| B4 | "Is Application_00001 compliant with SOX?" | Declines regulation / real-framework questions; offers dataset facts. |
| B5 | "Total open findings for the whole year" | Refuses to add across months; offers a monthly series. |
