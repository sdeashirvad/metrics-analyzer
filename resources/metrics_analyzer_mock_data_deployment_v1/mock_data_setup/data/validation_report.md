# Validation Report - Synthetic Enterprise Dataset

**Overall: PASS** - CSV checks 123/0/0 (PASS/WARN/FAIL), XLSX checks 123/0/0, file-integrity checks 8/0/0.

All checks were run against the **saved, re-loaded** CSV and XLSX files (not just the in-memory frame). No sample records are shown in this report.

## 1. Run information

| Item | Value |
|---|---|
| Generator version | 1.0.0 |
| Seed | 20261103 |
| Rows (excl. header) | 11,399 |
| Columns | 57 |
| CSV SHA-256 | 08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3 |
| Determinism (2nd full run identical) | yes |
| Generation time (s) | 19.9 |
| Dictionary source | Data_Dictionary_1.xlsx (57 columns, sheet state visible) |

Rule repairs applied by `enforce_rules` (safety net; 0 means the generator already produced compliant values):

| Repair | Rows touched |
|---|---|
| metric_date_realigned | 0 |
| month_year_rederived | 0 |
| rto_change_date_nulled | 0 |
| test_result_nulled_without_test | 0 |
| total_rfb_raised_to_rfb | 0 |
| numerator_clipped | 0 |
| department_nulled_at_super_level | 0 |
| bank_list_rederived | 0 |
| acquired_entity_inconsistent | 0 |

## 2. Schema, row and column counts

| Check | Status | Detail |
|---|---|---|
| Row count equals configured row_count | PASS | 11,399 vs 11,399 |
| Row count equals client contract (11,399) | PASS | 11,399 |
| Exactly 57 columns | PASS | 57 |
| Column names and order match specification | PASS |  |
| No duplicate column names | PASS |  |
| Spelling preserved: HAS_CTIRICAL_KBS and KBS_FLAG_FLAG | PASS |  |
| Seed equals contract seed 20261103 | PASS | 20261103 |
| Dictionary column order identical to specification | PASS | 57 dictionary rows |
| Every date / integer cell parses | PASS |  |
| Dates stored as ISO YYYY-MM-DD | PASS | 0 non-ISO cells |

## 3. Column types, missingness and distinct counts

| Column | Generated type | Nullable | Null count | Null rate | Distinct | Top-1 share |
|---|---|---|---|---|---|---|
| METRIC_ID | string | no | 0 | 0.00% | 24 | 17.2% |
| METRIC_DATE | date | no | 0 | 0.00% | 12 | 9.8% |
| METRIC_DATE_TYPE | string | no | 0 | 0.00% | 1 | 100.0% |
| IS_NUMERATOR | Int64 | no | 0 | 0.00% | 2 | 58.5% |
| IS_DENOMINATOR | Int64 | no | 0 | 0.00% | 2 | 79.9% |
| EON_ID | string | no | 0 | 0.00% | 1500 | 0.3% |
| BUILDING_NAME | string | no | 0 | 0.00% | 45 | 10.1% |
| EVENT_LOCATION | string | no | 0 | 0.00% | 32 | 11.1% |
| APPLICATION_TIER | Int64 | no | 0 | 0.00% | 4 | 38.5% |
| EXEMPTION_LEVEL_1 | string | yes | 10254 | 89.96% | 12 | 3.4% |
| TEST_STATUS | string | no | 0 | 0.00% | 4 | 66.4% |
| TEST_RESULT | string | yes | 3888 | 34.11% | 2 | 41.4% |
| SYSTEM_RTC | Int64 | no | 0 | 0.00% | 2 | 84.8% |
| RFB | Int64 | yes | 123 | 1.08% | 10 | 65.6% |
| TOTAL_RFB | Int64 | yes | 117 | 1.03% | 18 | 31.0% |
| COMPLIANCE_STATUS | string | no | 0 | 0.00% | 4 | 41.5% |
| COMPLIANCE_REASON | string | no | 0 | 0.00% | 18 | 25.7% |
| RTO_CHANGE_DATE | date | yes | 7445 | 65.31% | 460 | 0.4% |
| GRN | string | no | 0 | 0.00% | 1500 | 0.3% |
| APPLICATION_NAME | string | no | 0 | 0.00% | 1500 | 0.3% |
| APPLICATION_RTO | string | no | 0 | 0.00% | 6 | 26.2% |
| HAS_CTIRICAL_KBS | string | no | 0 | 0.00% | 2 | 75.6% |
| LIFECYCLE_PHASE | string | no | 0 | 0.00% | 5 | 60.3% |
| ASSET_RISK_RATING_2 | string | no | 0 | 0.00% | 4 | 39.5% |
| ARR_AVAILABILITY | string | no | 0 | 0.00% | 4 | 30.8% |
| ARR_CONFIDENTIALITY | string | no | 0 | 0.00% | 4 | 37.7% |
| ARR_INTEGRITY | string | no | 0 | 0.00% | 4 | 34.6% |
| IS_MERGERS_ACQUISITIONS_ASSET | string | no | 0 | 0.00% | 2 | 91.5% |
| ACQUIRED_ENTITY | string | no | 0 | 0.00% | 9 | 91.5% |
| BU_SUPER_DIVISION | string | no | 0 | 0.00% | 6 | 28.1% |
| BU_DIVISION | string | no | 0 | 0.00% | 16 | 21.3% |
| BU_SUPER_DEPARTMENT | string | no | 0 | 0.00% | 39 | 14.9% |
| BU_DEPARTMENT | string | yes | 1271 | 11.15% | 76 | 12.1% |
| ORG_GROUP_TYPE | string | no | 0 | 0.00% | 2 | 88.8% |
| SUPER_DIVISION | string | no | 0 | 0.00% | 8 | 21.3% |
| DIVISION | string | no | 0 | 0.00% | 26 | 11.8% |
| SUPER_DEPARTMENT | string | no | 0 | 0.00% | 79 | 8.9% |
| DEPARTMENT | string | yes | 1271 | 11.15% | 214 | 7.1% |
| BUS_ORG_LG_NM | string | no | 0 | 0.00% | 278 | 7.1% |
| COST_CENTER_CODE | string | no | 0 | 0.00% | 272 | 8.5% |
| COST_CENTER_NAME | string | no | 0 | 0.00% | 272 | 8.5% |
| EMPLOYEE_BUILDING_NAME | string | no | 0 | 0.00% | 41 | 9.7% |
| EMPLOYEE_COUNTRY_NAME | string | no | 0 | 0.00% | 7 | 44.3% |
| PRIMARY_BUS_FIRST_NAME | string | no | 0 | 0.00% | 402 | 2.9% |
| PRIMARY_BUS_LAST_NAME | string | no | 0 | 0.00% | 384 | 3.0% |
| PRIMARY_IT_FIRST_NAME | string | no | 0 | 0.00% | 326 | 4.2% |
| PRIMARY_IT_LAST_NAME | string | no | 0 | 0.00% | 315 | 4.2% |
| LEGAL_ENTITY_CODE | string | no | 0 | 0.00% | 40 | 4.7% |
| LEGAL_ENTITY_NAME | string | no | 0 | 0.00% | 40 | 4.7% |
| IS_USBANKS | string | no | 0 | 0.00% | 2 | 59.5% |
| IS_MSBNA | string | no | 0 | 0.00% | 2 | 64.1% |
| IS_MSPBNA | string | no | 0 | 0.00% | 2 | 94.9% |
| USBANKS_LE_LIST | string | yes | 1996 | 17.51% | 5 | 41.5% |
| KBS_FLAG_FLAG | string | no | 0 | 0.00% | 2 | 75.6% |
| REPORTING_MONTHEND_DATE | date | no | 0 | 0.00% | 12 | 9.8% |
| REPORTING_MONTH | Int64 | no | 0 | 0.00% | 12 | 9.8% |
| REPORTING_YEAR | Int64 | no | 0 | 0.00% | 2 | 87.2% |

## 4. Top categorical shares (columns with <= 60 distinct values)

| Column | Distinct | Top values (share of rows) |
|---|---|---|
| METRIC_ID | 24 | M340202 17.2%; M384010 11.5%; M346318 9.2%; M325402 6.9% |
| METRIC_DATE_TYPE | 1 | Monthend 100.0% |
| IS_NUMERATOR | 2 | 0 58.5%; 1 41.5% |
| IS_DENOMINATOR | 2 | 1 79.9%; 0 20.1% |
| BUILDING_NAME | 45 | Building_042 10.1%; Building_006 7.1%; Building_020 4.9%; Building_033 4.5% |
| EVENT_LOCATION | 32 | Location_010 11.1%; Location_006 8.1%; Location_005 6.8%; Location_001 5.4% |
| APPLICATION_TIER | 4 | 3 38.5%; 2 30.9%; 4 20.5%; 1 10.0% |
| EXEMPTION_LEVEL_1 | 12 | Exemption_09 3.4%; Exemption_12 1.9%; Exemption_01 1.0%; Exemption_07 0.8% |
| TEST_STATUS | 4 | Test_Complete 66.4%; No_Test 15.1%; Test_Pending 10.0%; Exempt 8.4% |
| TEST_RESULT | 2 | Pass 41.4%; Fail 24.5% |
| SYSTEM_RTC | 2 | 0 84.8%; 1 15.2% |
| RFB | 10 | 0 65.6%; 1 9.1%; 2 8.3%; 3 6.9% |
| TOTAL_RFB | 18 | 0 31.0%; 1 22.2%; 2 13.2%; 3 9.5% |
| COMPLIANCE_STATUS | 4 | Compliant 41.5%; Non_Compliant 30.1%; Pending 16.9%; Not_Applicable 11.6% |
| COMPLIANCE_REASON | 18 | Requirements_Met 25.7%; Test_Failed 10.7%; Open_Findings_Outstanding 8.4%; Controls_Verified 7.5% |
| APPLICATION_RTO | 6 | RTO_4_12H 26.2%; RTO_12_24H 23.6%; RTO_1_4H 18.5%; RTO_24_72H 17.3% |
| HAS_CTIRICAL_KBS | 2 | N 75.6%; Y 24.4% |
| LIFECYCLE_PHASE | 5 | Production 60.3%; Retirement 11.9%; Development 11.3%; Implementation 8.4% |
| ASSET_RISK_RATING_2 | 4 | P3 39.5%; P2 39.5%; P4 10.6%; P1 10.4% |
| ARR_AVAILABILITY | 4 | A2 30.8%; A3 30.7%; A1 19.6%; A4 18.9% |
| ARR_CONFIDENTIALITY | 4 | C3 37.7%; C2 29.3%; C4 20.7%; C1 12.2% |
| ARR_INTEGRITY | 4 | I2 34.6%; I3 30.8%; I1 19.1%; I4 15.6% |
| IS_MERGERS_ACQUISITIONS_ASSET | 2 | N 91.5%; Y 8.5% |
| ACQUIRED_ENTITY | 9 | NON_ACQUIRED_ENTITY 91.5%; Acquired_Entity_04 2.1%; Acquired_Entity_03 2.0%; Acquired_Entity_05 1.1% |
| BU_SUPER_DIVISION | 6 | BU_Super_Division_01 28.1%; BU_Super_Division_05 26.9%; BU_Super_Division_03 16.9%; BU_Super_Division_04 13.1% |
| BU_DIVISION | 16 | BU_Division_05_02 21.3%; BU_Division_01_02 14.2%; BU_Division_03_02 13.1%; BU_Division_02_01 7.9% |
| BU_SUPER_DEPARTMENT | 39 | BU_Super_Department_05_02_01 14.9%; BU_Super_Department_01_02_01 11.1%; BU_Super_Department_03_02_03 6.5%; BU_Super_Department_03_02_02 6.2% |
| ORG_GROUP_TYPE | 2 | DEPARTMENT 88.8%; SUPER_DEPARTMENT 11.2% |
| SUPER_DIVISION | 8 | Super_Division_04 21.3%; Super_Division_02 15.0%; Super_Division_06 14.4%; Super_Division_05 14.3% |
| DIVISION | 26 | Division_06_02 11.8%; Division_04_02 10.4%; Division_08_02 6.7%; Division_05_01 5.0% |
| EMPLOYEE_BUILDING_NAME | 41 | Building_006 9.7%; Building_020 7.0%; Building_042 6.7%; Building_023 6.4% |
| EMPLOYEE_COUNTRY_NAME | 7 | Country_05 44.3%; Country_04 21.0%; Country_06 10.4%; Country_03 8.5% |
| LEGAL_ENTITY_CODE | 40 | LE2590 4.7%; LE4955 4.5%; LE4023 4.4%; LE4621 4.4% |
| LEGAL_ENTITY_NAME | 40 | Legal_Entity_38 4.7%; Legal_Entity_04 4.5%; Legal_Entity_34 4.4%; Legal_Entity_40 4.4% |
| IS_USBANKS | 2 | Y 59.5%; N 40.5% |
| IS_MSBNA | 2 | N 64.1%; Y 35.9% |
| IS_MSPBNA | 2 | N 94.9%; Y 5.1% |
| USBANKS_LE_LIST | 5 | BANK_A 41.5%; BANK_B 21.4%; BANK_A\|BANK_B 14.5%; BANK_A\|BANK_C 3.5% |
| KBS_FLAG_FLAG | 2 | N 75.6%; Y 24.4% |
| REPORTING_MONTH | 12 | 8 9.8%; 10 9.6%; 9 9.6%; 7 9.4% |
| REPORTING_YEAR | 2 | 2026 87.2%; 2025 12.8% |

Long-tail indicator (share of a column's distinct values holding < 1% of rows) for high-cardinality columns:

| Column | Distinct | Top-1 share | Share of values < 1% of rows |
|---|---|---|---|
| EON_ID | 1500 | 0.3% | 100% |
| METRIC_ID | 24 | 17.2% | 0% |
| COST_CENTER_CODE | 272 | 8.5% | 94% |
| LEGAL_ENTITY_CODE | 40 | 4.7% | 10% |
| BUILDING_NAME | 45 | 10.1% | 42% |
| DEPARTMENT | 214 | 7.1% | 93% |
| PRIMARY_BUS_LAST_NAME | 384 | 3.0% | 96% |
| EXEMPTION_LEVEL_1 | 12 | 3.4% | 75% |

## 5. Reporting period coverage

| Date | Rows | Distinct EON_ID | Distinct METRIC_ID | Compliant | Non_Compliant | Pending | Not_Applicable | Failed tests | Provisional compliance rate |
|---|---|---|---|---|---|---|---|---|---|
| 2025-11-30 | 699 | 596 | 24 | 304 | 216 | 99 | 80 | 168 | 0.5305 |
| 2025-12-31 | 763 | 652 | 24 | 320 | 221 | 138 | 84 | 175 | 0.5229 |
| 2026-01-31 | 827 | 708 | 24 | 349 | 252 | 130 | 96 | 202 | 0.5304 |
| 2026-02-28 | 859 | 745 | 24 | 351 | 265 | 155 | 88 | 206 | 0.5029 |
| 2026-03-31 | 908 | 780 | 24 | 375 | 287 | 144 | 102 | 247 | 0.5095 |
| 2026-04-30 | 943 | 814 | 24 | 385 | 288 | 159 | 111 | 248 | 0.5086 |
| 2026-05-31 | 978 | 842 | 24 | 400 | 308 | 171 | 99 | 257 | 0.5031 |
| 2026-06-30 | 1046 | 903 | 24 | 445 | 304 | 171 | 126 | 246 | 0.5374 |
| 2026-07-31 | 1068 | 922 | 24 | 420 | 328 | 194 | 126 | 264 | 0.497 |
| 2026-08-31 | 1117 | 962 | 24 | 457 | 345 | 178 | 137 | 269 | 0.5141 |
| 2026-09-30 | 1095 | 937 | 24 | 456 | 296 | 199 | 144 | 237 | 0.5416 |
| 2026-10-31 | 1096 | 923 | 24 | 463 | 324 | 183 | 126 | 273 | 0.5304 |

Date columns: METRIC_DATE: 2025-11-30 to 2026-10-31 (12 distinct); RTO_CHANGE_DATE: 2023-11-02 to 2026-10-31 (460 distinct); REPORTING_MONTHEND_DATE: 2025-11-30 to 2026-10-31 (12 distinct)

## 6. Entity repetition statistics

| Statistic | Value |
|---|---|
| Distinct EON_ID | 1500 |
| Distinct METRIC_ID | 24 |
| Rows per EON_ID (min / p25 / median / mean / p75 / p90 / max) | 1.0 / 3.0 / 6.0 / 7.599 / 12.0 / 12.0 / 36.0 |
| Periods observed per EON_ID (same stats) | 1.0 / 3.0 / 6.0 / 6.523 / 11.25 / 12.0 / 12.0 |
| Metrics per EON_ID histogram | {'1': 1105, '2': 315, '3': 80} |
| Share of apps in 2+ / 6+ / all periods | 90.7% / 51.3% / 25.0% |
| Share of apps with a single observation | 7.2% |
| Top-10% apps' share of rows / largest single app | 24.6% / 0.32% |
| Rows per METRIC_ID (min / median / max) | 127 / 340 / 1955 |

Applications by number of periods observed:

| Periods observed | Applications |
|---|---|
| 1 | 139 |
| 2 | 172 |
| 3 | 149 |
| 4 | 134 |
| 5 | 136 |
| 6 | 99 |
| 7 | 80 |
| 8 | 79 |
| 9 | 50 |
| 10 | 55 |
| 11 | 32 |
| 12 | 375 |

## 7. Application stability within EON_ID

| Attribute group | Multi-row apps | Apps with a change | Rows off the app's modal value |
|---|---|---|---|
| application_name_grn | 1392 | 0.00% | 0.00% |
| application_tier | 1392 | 2.95% | 0.93% |
| application_rto | 1392 | 3.66% | 1.18% |
| lifecycle_phase | 1392 | 3.81% | 1.04% |
| risk_ratings | 1392 | 3.30% | 0.91% |
| critical_kbs_flags | 1392 | 0.00% | 0.00% |
| ma_fields | 1392 | 0.00% | 0.00% |
| business_owner | 1392 | 3.66% | 1.04% |
| it_owner | 1392 | 2.80% | 0.83% |
| organisation_both_hierarchies | 1392 | 2.01% | 0.63% |
| cost_centre | 1392 | 2.51% | 0.78% |
| legal_entity_and_flags | 1392 | 1.58% | 0.39% |
| primary_building_location | 1392 | 1.87% | 0.46% |
| employee_building_country | 1392 | 3.23% | 0.96% |

Shares are among applications with 2+ rows. Configured change probabilities are per application over the window; observed shares sit close to them (sampling noise about +/-1pp). Single-row applications cannot show change (see assumptions F01).

## 8. Hierarchy, lookup and mapping consistency

| Check | Status | Detail |
|---|---|---|
| DIVISION has exactly one SUPER_DIVISION | PASS |  |
| SUPER_DEPARTMENT has exactly one DIVISION | PASS |  |
| DEPARTMENT has exactly one SUPER_DEPARTMENT | PASS |  |
| BU_DIVISION has exactly one BU_SUPER_DIVISION | PASS |  |
| BU_SUPER_DEPARTMENT has exactly one BU_DIVISION | PASS |  |
| BU_DEPARTMENT has exactly one BU_SUPER_DEPARTMENT | PASS |  |
| Hierarchy 2 paths exist in the lookup | PASS |  |
| Hierarchy 1 (BU_) paths exist in the lookup | PASS |  |
| DEPARTMENT deterministically maps to one BU_DEPARTMENT | PASS |  |
| ORG_GROUP_TYPE consistent with populated level (DEPARTMENT => both dept cols; SUPER_DEPARTMENT => both null) | PASS | 11.2% rows at super-department level |
| BUS_ORG_LG_NM consistent with hierarchy | PASS |  |
| COST_CENTER_CODE <-> COST_CENTER_NAME one-to-one | PASS |  |
| Cost-centre code/name pairs match the lookup | PASS |  |
| Cost centre belongs to the row's DEPARTMENT | PASS |  |
| LEGAL_ENTITY_CODE <-> LEGAL_ENTITY_NAME one-to-one | PASS |  |
| Legal-entity code/name pairs match the lookup | PASS |  |
| Bank-grouping flags are a function of the legal entity | PASS |  |
| USBANKS_LE_LIST agrees with IS_USBANKS / IS_MSBNA / IS_MSPBNA (null iff all N) | PASS | 17.5% null |
| EVENT_LOCATION deterministic from BUILDING_NAME (location lookup) | PASS |  |
| BUILDING_NAME / EMPLOYEE_BUILDING_NAME come from the building lookup | PASS |  |
| EMPLOYEE_COUNTRY_NAME deterministic from EMPLOYEE_BUILDING_NAME | PASS |  |
| ACQUIRED_ENTITY agrees with IS_MERGERS_ACQUISITIONS_ASSET | PASS |  |
| KBS_FLAG_FLAG consistent with HAS_CTIRICAL_KBS | PASS | 0.00% disagree |

## 9. Compliance and testing consistency

| Check | Status | Detail |
|---|---|---|
| TEST_RESULT null whenever no completed test | PASS | 0 violations |
| Test_Complete rows nearly always carry Pass/Fail | PASS | 99.17% |
| (COMPLIANCE_STATUS, TEST_STATUS, TEST_RESULT) combinations are all permitted | PASS | 17 combinations used |
| COMPLIANCE_REASON consistent with COMPLIANCE_STATUS and TEST_STATUS | PASS | 0 violations |
| No-test rows carry a synthetic no-test reason or pending/NA reason (never a 'Test_Failed'/'Requirements_Met' reason) | PASS |  |
| EXEMPTION_LEVEL_1 usually populated when Exempt | PASS | 96.9% |
| EXEMPTION_LEVEL_1 mostly blank otherwise | PASS | 2.1% populated |
| TOTAL_RFB >= RFB where both numeric | PASS | 0 violations |
| RFB normally zero for compliant rows | PASS | 92.1% zero |
| SYSTEM_RTC=1 more likely for non-compliant than compliant rows | PASS | 34.7% vs 5.8% |
| IS_NUMERATOR <= IS_DENOMINATOR | PASS |  |
| IS_DENOMINATOR / IS_NUMERATOR follow the provisional metric-variant rule | PASS | provisional rule, not a client definition |

## 10. Keys, nulls and domains

| Check | Status | Detail |
|---|---|---|
| All non-nullable columns fully populated (keys, reporting fields, hierarchy levels 1-3, ...) | PASS | 49 columns checked |
| Nulls are true missing values (no 'NULL'/'nan'/'None'/blank-string tokens) | PASS |  |
| Identifier columns are text (not numeric) | PASS |  |
| IS_NUMERATOR in {0,1} | PASS |  |
| IS_DENOMINATOR in {0,1} | PASS |  |
| SYSTEM_RTC in {0,1} | PASS |  |
| APPLICATION_TIER in 1..4 | PASS |  |
| REPORTING_MONTH in 1..12 and REPORTING_YEAR 4-digit | PASS |  |
| RFB and TOTAL_RFB non-negative integers where present | PASS |  |
| HAS_CTIRICAL_KBS contains only Y/N | PASS |  |
| IS_MERGERS_ACQUISITIONS_ASSET contains only Y/N | PASS |  |
| IS_USBANKS contains only Y/N | PASS |  |
| IS_MSBNA contains only Y/N | PASS |  |
| IS_MSPBNA contains only Y/N | PASS |  |
| KBS_FLAG_FLAG contains only Y/N | PASS |  |
| ASSET_RISK_RATING_2 codes valid (P[1-4]) | PASS |  |
| ARR_AVAILABILITY codes valid (A[1-4]) | PASS |  |
| ARR_CONFIDENTIALITY codes valid (C[1-4]) | PASS |  |
| ARR_INTEGRITY codes valid (I[1-4]) | PASS |  |
| TEST_STATUS vocabulary valid | PASS |  |
| COMPLIANCE_STATUS vocabulary valid | PASS |  |
| TEST_RESULT only Pass/Fail/null | PASS |  |
| LIFECYCLE_PHASE vocabulary valid | PASS |  |
| APPLICATION_RTO vocabulary valid | PASS |  |
| METRIC_DATE_TYPE vocabulary valid | PASS |  |

## 11. Dates

| Check | Status | Detail |
|---|---|---|
| METRIC_DATE equals REPORTING_MONTHEND_DATE on every row | PASS |  |
| REPORTING_MONTHEND_DATE is a month-end | PASS |  |
| Reporting dates are exactly the configured consecutive month-ends | PASS | 12 periods 2025-11-30..2026-10-31 |
| REPORTING_MONTH derived correctly | PASS |  |
| REPORTING_YEAR derived correctly | PASS |  |
| RTO_CHANGE_DATE null or <= METRIC_DATE | PASS | 0 violations |
| RTO_CHANGE_DATE missingness is moderate/high (often missing) | PASS | 65.3% null |

## 12. Entity identity

| Check | Status | Detail |
|---|---|---|
| EON_ID <-> APPLICATION_NAME one-to-one | PASS |  |
| EON_ID <-> GRN one-to-one | PASS |  |
| GRN suffix agrees with APPLICATION_NAME | PASS |  |
| Generated application set equals entity lookup | PASS | 1500 vs 1500 |
| Stable within EON_ID: application_name_grn | PASS | 0.00% of multi-row apps change; 0.00% rows off modal |
| Stable within EON_ID: application_tier | PASS | 2.95% of multi-row apps change; 0.93% rows off modal |
| Stable within EON_ID: application_rto | PASS | 3.66% of multi-row apps change; 1.18% rows off modal |
| Stable within EON_ID: lifecycle_phase | PASS | 3.81% of multi-row apps change; 1.04% rows off modal |
| Stable within EON_ID: risk_ratings | PASS | 3.30% of multi-row apps change; 0.91% rows off modal |
| Stable within EON_ID: critical_kbs_flags | PASS | 0.00% of multi-row apps change; 0.00% rows off modal |
| Stable within EON_ID: ma_fields | PASS | 0.00% of multi-row apps change; 0.00% rows off modal |
| Stable within EON_ID: business_owner | PASS | 3.66% of multi-row apps change; 1.04% rows off modal |
| Stable within EON_ID: it_owner | PASS | 2.80% of multi-row apps change; 0.83% rows off modal |
| Stable within EON_ID: organisation_both_hierarchies | PASS | 2.01% of multi-row apps change; 0.63% rows off modal |
| Stable within EON_ID: cost_centre | PASS | 2.51% of multi-row apps change; 0.78% rows off modal |
| Stable within EON_ID: legal_entity_and_flags | PASS | 1.58% of multi-row apps change; 0.39% rows off modal |
| Stable within EON_ID: primary_building_location | PASS | 1.87% of multi-row apps change; 0.46% rows off modal |
| Stable within EON_ID: employee_building_country | PASS | 3.23% of multi-row apps change; 0.96% rows off modal |
| Business-owner (first,last) pairs all exist in the fictional-person lookup | PASS | 412 pairs |
| IT-owner (first,last) pairs all exist in the fictional-person lookup | PASS | 334 pairs |
| Business-owner pair maps to a single employee building | PASS | max 1 |

Cross-tab TEST_STATUS x COMPLIANCE_STATUS (rows):

| TEST_STATUS | Compliant | Non_Compliant | Not_Applicable | Pending |
|---|---|---|---|---|
| Exempt | 135 | 71 | 754 | 0 |
| No_Test | 0 | 533 | 565 | 626 |
| Test_Complete | 4590 | 2679 | 0 | 305 |
| Test_Pending | 0 | 151 | 0 | 990 |

## 13. Duplicate and candidate-key analysis

| Key | Duplicate rows |
|---|---|
| EON_ID+METRIC_ID+METRIC_DATE (candidate row key) | 0 |
| full_row | 0 |
| EON_ID+METRIC_DATE (several metrics per app-month; informational) | 1615 |
| EON_ID+METRIC_ID (repeats across months; informational) | 9424 |
| METRIC_ID+METRIC_DATE (repeats across apps; informational) | 11111 |

Row grain: one row = (EON_ID, METRIC_ID, REPORTING_MONTHEND_DATE). METRIC_ID repeats by design (grouping pattern: Zipf-weighted primary metric per app, same-family secondary metrics - see assumptions B03).

## 14. Scenario coverage and longitudinal change

| Scenario | Entities | Rows | Non_Compliant | Compliant | Test_Complete | Test_Pending | Exempt | No_Test | Fail share (completed) | NC before/after switch |
|---|---|---|---|---|---|---|---|---|---|---|
| consistently_compliant | 476 | 3484 | 10.1% | 79.4% | 90.2% | 4.0% | 2.1% | 3.8% | 5.0% |  |
| deteriorating | 94 | 991 | 41.3% | 43.3% | 85.3% | 5.1% | 2.8% | 6.8% | 47.8% | 14.5% -> 61.6% |
| exempt | 111 | 779 | 8.9% | 15.9% | 3.9% | 3.9% | 87.7% | 4.6% | 23.3% |  |
| improving_after_remediation | 107 | 1093 | 40.1% | 44.5% | 85.3% | 5.7% | 1.9% | 7.1% | 47.0% | 65.3% -> 20.0% |
| no_completed_tests | 127 | 804 | 38.4% | 0.5% | 0.0% | 3.6% | 6.8% | 89.5% |  |  |
| not_applicable_scope | 59 | 359 | 10.0% | 4.2% | 4.5% | 1.1% | 3.9% | 90.5% | 12.5% |  |
| pending_tests | 103 | 656 | 15.4% | 4.1% | 5.5% | 85.2% | 4.6% | 4.7% | 33.3% |  |
| persistently_noncompliant | 240 | 1640 | 66.1% | 13.2% | 79.6% | 6.3% | 1.9% | 12.1% | 88.3% |  |
| volatile_mixed | 183 | 1593 | 40.0% | 41.2% | 79.5% | 10.4% | 1.6% | 8.6% | 48.8% |  |

Month-to-month transitions over 7,968 consecutive observed application-month pairs: **1,296 new non-compliance**, **1,311 resolved**, 1,285 persistent. (entity-month flag = any Non_Compliant row for the EON_ID in that month; consecutive observed months only)

Risk code vs compliance (no artificial coupling expected):

| ASSET_RISK_RATING_2 | Rows | Non_Compliant share | Fail share of completed tests |
|---|---|---|---|
| P1 | 1189 | 31.9% | 39.4% |
| P2 | 4502 | 29.5% | 35.4% |
| P3 | 4503 | 29.9% | 37.4% |
| P4 | 1205 | 31.6% | 38.0% |

Longitudinal checks:

| Check | Status | Detail |
|---|---|---|
| Candidate key (EON_ID, METRIC_ID, METRIC_DATE) is unique | PASS | 0 |
| No fully duplicated rows | PASS | 0 |
| METRIC_ID values all come from the metric catalogue | PASS | 24 used of 24 |
| METRIC_ID repeats across applications and periods (not a row key) | PASS | rows/metric min 127 max 1955 |
| Distinct EON_ID within target range | PASS | 1500 |
| Meaningful share of applications observed in 2+ periods | PASS | 90.7% |
| Meaningful share of applications observed in 6+ periods | PASS | 51.3% |
| Dataset is not a full Cartesian grid (sparse history present) | PASS | 25.0% fully observed, 7.2% single observation |
| Heavy-tailed observations per application (top 10% of apps hold well above 10% of rows) | PASS | 24.6% |
| Every reporting period has data | PASS | min 699 max 1117 rows/period |
| Month-to-month new non-compliance observed | PASS | 1296 |
| Month-to-month remediation (non-compliance resolved) observed | PASS | 1311 |
| Provisional compliance rate varies across months (trend demonstrable) | PASS | range 0.497-0.542 |
| All configured scenarios are present | PASS | 9 scenarios |
| consistently_compliant: Non_Compliant share <= 15% | PASS | 0.1007 |
| persistently_noncompliant: Non_Compliant share >= 60% | PASS | 0.661 |
| deteriorating: Non_Compliant share rises after the switch month | PASS | 0.14 -> 0.62 |
| improving_after_remediation: Non_Compliant share falls after the switch month | PASS | 0.65 -> 0.20 |
| no_completed_tests: zero Test_Complete rows | PASS | 0.0 |
| pending_tests: Test_Pending dominates | PASS | 0.8521 |
| exempt: Exempt dominates | PASS | 0.8768 |
| No artificial risk/compliance coupling: each risk code has a mixed Non_Compliant share (5%-80%) | PASS | {'P1': 0.3188, 'P2': 0.2952, 'P3': 0.2987, 'P4': 0.3162} |
| Failed completed tests occur in every asset-risk code | PASS |  |

## 15. Privacy / disclosure scan

| Item | Result |
|---|---|
| Status | PASS |
| Findings | 0 |
| String columns scanned | 46 |
| Distinct string values scanned | 7,538 |
| Findings by check | none |
| Scanner self-test (planted violations detected) | PASS |

The scan applies to cell values only (column names keep the client's legacy spelling by instruction). The embedded deny-lists are not exhaustive; extend `validation.extra_forbidden_terms`.

## 16. Saved-file integrity (CSV vs XLSX vs in-memory)

| Check | Status | Detail |
|---|---|---|
| CSV is valid UTF-8 without BOM | PASS |  |
| CSV header row equals the 57 specified column names | PASS |  |
| Saved CSV equals the in-memory frame cell-by-cell | PASS |  |
| XLSX Data sheet equals CSV cell-by-cell | PASS |  |
| Same configuration + seed regenerates an identical dataset | PASS |  |
| Workbook has the four required worksheets in order | PASS | ['Data', 'Data Dictionary', 'Validation Summary', 'Assumptions'] |
| Data Dictionary sheet lists all 57 columns | PASS | 57 |
| Final XLSX (after summary rewrite) still equals CSV cell-by-cell | PASS |  |

Full validation was also repeated on the re-loaded XLSX `Data` sheet: 123 PASS / 0 WARN / 0 FAIL (identical outcome to the CSV run).

## 17. Failed and warning-level checks

None - every check passed.

## 18. Candidate golden questions

| ID | Question | Status | SQL == pandas |
|---|---|---|---|
| Q01 | How many distinct applications reported in October 2026? | Unambiguous | yes |
| Q02 | How many applications reported in all 12 periods? | Unambiguous | yes |
| Q03 | How many rows are in each COMPLIANCE_STATUS in October 2026? | Unambiguous | yes |
| Q04 | What is the provisional compliance rate by reporting month? | PROVISIONAL (numerator/denominator rule is a generator assumption) | yes |
| Q05 | How many completed tests failed in each month? | Unambiguous | yes |
| Q06 | Which 5 SUPER_DIVISIONs have the most non-compliant applications in October 2026? | Unambiguous (an application counts once if any of its rows is Non_Compliant) | yes |
| Q07 | How many applications became non-compliant in October 2026? | PROVISIONAL (definition of 'newly non-compliant' is an analyst assumption) | yes |
| Q08 | Which 5 legal entities hold the most distinct applications in October 2026? | Unambiguous | yes |
| Q09 | How many M&A-associated applications have a non-compliant row in October 2026? | Unambiguous | yes |
| Q10 | Which 5 primary business owners (fictional) own the most applications in October 2026? | Unambiguous | yes |
| Q11 | What is the average RFB per COMPLIANCE_STATUS in October 2026? | PROVISIONAL (RFB semantics are a generator assumption) | yes |
| Q12 | What share of completed tests failed, by ASSET_RISK_RATING_2 (all months)? | PROVISIONAL (risk-code severity direction is not defined by the sources) | yes |

Full SQL and expected results: `golden_questions.md`.

## 19. Limitations

- All distributions are generator assumptions; nothing here is statistically equivalent to the confidential client data.
- Numerator/denominator, RFB/TOTAL_RFB, SYSTEM_RTC, tier direction and risk-code direction are provisional (assumptions register C03-C05, D01-D03).
- Reporting population grows over the window (about 600 applications in the first month, about 900-960 in the last) because applications enter the window at different months; use rates/shares rather than absolute counts when demonstrating monthly trends (assumptions B05, G06).
- The aggregate provisional compliance rate is roughly flat (deteriorating and improving applications offset each other); month-to-month change is concentrated at application / organisation level (new and resolved non-compliance).
- The disclosure scan uses embedded, non-exhaustive deny-lists.
- The Word prompt's Part 3 line on owner name pairs is truncated in the source; the dictionary rule was used instead (A02).
