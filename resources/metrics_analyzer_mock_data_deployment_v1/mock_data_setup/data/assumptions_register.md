# Assumptions Register - Metrics Analyzer synthetic dataset

Everything below is a **synthetic-generation decision**. Items marked *Provisional* are NOT confirmed client business definitions and are configurable in `PROFILE_CONFIG`.
Unresolved or provisional definitions must be confirmed by the client before they are used as semantic definitions in the Metrics Analyzer / Cortex Agent.

## Source handling, conflicts and gaps

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| A01 | Source handling | Data_Dictionary_1.xlsx is the primary reference for column names, types, examples, nullability, vocabularies and relationships; the Word prompt supplies counts, column order, privacy rules, relationships and validation requirements. Dictionary has one visible worksheet (no hidden sheets, comments or defined names); its 57 columns are in exactly the same order as Part 1 of the Word prompt. | Source-derived | - |
| A02 | Source gap | Part 3 of the Word prompt is truncated at 'PRIMARY_BUS_FIRST_NAME/LAST_NAME and PRIMARY_IT_FIRST_NAME/LAST_NAME must be stable fictional person pairs, generally ...' ('continuation not visible'). The missing text was NOT invented. Interpretation taken from the dictionary ('stable pair for an EON_ID'): a (first,last) pair is a single fictional person and is stable within EON_ID except for a controlled owner-change rate. | Gap in source | change_rates.bus_owner / it_owner |
| A03 | Source conflict | ACQUIRED_ENTITY: the Word prompt lists acquisition fields among columns with moderate/high null rates, but the dictionary example is NON_ACQUIRED_ENTITY and its rule says the column 'must agree with IS_MERGERS_ACQUISITIONS_ASSET'. Decision: dictionary governs - ACQUIRED_ENTITY is never null; 'N' => NON_ACQUIRED_ENTITY, 'Y' => a fictional Acquired_Entity_NN. | Conflict resolved (dictionary wins) | entity.ma_rate |
| A04 | Source conflict | Identifier formats: the Word prompt asks for 'unrelated ranges and prefixes'; the dictionary's synthetic examples use the prefixes EON / M / CC / LE and the grn:/synthetic/domain/ URI. Decision: keep the dictionary prefixes so the data loads into the planned schema unchanged, but draw all numeric parts from ranges disjoint from the dictionary examples. Prefixes are configurable; the disclosure scan range-checks them. If any prefix is considered proprietary, change id_prefixes and re-run. | Conflict resolved (compromise) | id_prefixes, id_ranges |
| A05 | Source conflict | Naming conventions: the Word prompt lists neutral patterns such as Person_0001 and Division_01; the dictionary shows hierarchical labels (BU_Division_04_03, Department_07_01_01_01) and syllable-style person names (Quinve, LiaHa). Decision: dictionary label patterns are used for organisation fields; people are built from internal syllable lists (both sources allow this) and checked against a real-name deny-list. | Conflict resolved | - |
| A06 | Source gap | Neither file supplies real-data distributions. Every probability vector is a plausible enterprise-style assumption (dominant / medium / long-tail categories). The output must NOT be described as statistically equivalent to the client's data; it only reproduces schema, relationships and qualitative shapes. | Gap in source | entity.*, scenarios.*, rules.* |
| A07 | Privacy | Legacy column names IS_USBANKS, IS_MSBNA, IS_MSPBNA are kept verbatim. Their values are generic Y/N and USBANKS_LE_LIST uses BANK_A\|BANK_B\|BANK_C. Mapping IS_USBANKS->BANK_A, IS_MSBNA->BANK_B, IS_MSPBNA->BANK_C is a generator convention, not a statement about any institution. | Provisional | entity.bank_flag_rates |
| A08 | Privacy | Disclosure scan = e-mail/URL regex + deny-list of firm/bank/brand tokens + real first/last-name lists + per-column shape whitelist + ID-range check. The embedded deny-lists are NOT exhaustive; extend validation.extra_forbidden_terms for site-specific terms. | Provisional | validation.extra_forbidden_terms |
| A09 | Schema | HAS_CTIRICAL_KBS and KBS_FLAG_FLAG spellings preserved. KBS_FLAG_FLAG equals HAS_CTIRICAL_KBS on every row by default ('generated consistently'); a disagreement rate can be configured. | Provisional | entity.kbs_flag_disagreement_rate |

## Grain, cardinality and reporting period

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| B01 | Row grain | One row = one observation of one METRIC_ID for one application (EON_ID) at one month-end. Candidate key (EON_ID, METRIC_ID, METRIC_DATE) is unique. METRIC_ID is NOT a row key and repeats across applications and months. The true aggregation grain of every client METRIC_ID is unknown. | Provisional | - |
| B02 | Cardinality | 1,500 synthetic applications (EON_ID), inside the requested 1,000-2,000 band. Each has a fixed APPLICATION_NAME and GRN. | Provisional | cardinality.n_entities |
| B03 | Cardinality | 24 metrics in 6 families. Each application has a Zipf-weighted primary metric (72% of apps have one metric, 22% two, 6% three; secondary metrics come from the primary's family 70% of the time). Metrics differ only by denominator-scope variant (A/B) and a small failure-probability offset; they carry no business meaning. | Provisional | cardinality.n_metrics, observations.* |
| B04 | Reporting period | 12 consecutive month-ends ending 2026-10-31 (Nov-2025 .. Oct-2026). Date span, month count and METRIC_DATE_TYPE vocabulary are configurable; the dictionary does not override this default. | Provisional | reporting.* |
| B05 | Longitudinal sparsity | The fixed 11,399-row budget is spread over applications with a heavy-tailed number of observations (lognormal, then capped by metric x month capacity). Each application is observed inside a contiguous window (50% anchored to the latest month = still reporting, 15% anchored to the first month, 35% random) with occasional gaps. The result is intentionally sparse, not a Cartesian grid. Side effect: the reporting population grows over the window (rows per month rise from roughly 700 to roughly 1,100) because windows are anchored towards the latest month; absolute counts therefore trend upwards by construction. | Provisional | observations.* |

## Compliance, testing and numerical rules

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| C01 | Compliance / test rules | COMPLIANCE_STATUS, COMPLIANCE_REASON, TEST_STATUS, TEST_RESULT, EXEMPTION_LEVEL_1, SYSTEM_RTC, RFB, TOTAL_RFB, IS_NUMERATOR and IS_DENOMINATOR are generated jointly from the rule tables in rules.* conditioned on scenario, month and metric. Reason vocabulary (apart from Requirements_Met from the dictionary example) is invented and keyed by COMPLIANCE_STATUS\|TEST_STATUS\|TEST_RESULT. | Provisional | rules.* |
| C02 | Compliance / test rules | TEST_RESULT is Pass/Fail only when TEST_STATUS = Test_Complete (0.8% of those rows have a missing result as a deliberate data-quality gap); it is null for Test_Pending, Exempt and No_Test. Tests that fail do not always give Non_Compliant (and passes not always Compliant) so outcomes are not perfectly correlated. | Provisional | missingness.TEST_RESULT_when_test_complete |
| C03 | Numerator / denominator | NOT a confirmed business rule. Metric variant A: denominator = Compliant + Non_Compliant; variant B: also includes Pending; Not_Applicable is never in a denominator; numerator = Compliant rows inside the denominator. The sources only say 'interpretation depends on the metric definition'. | Provisional | rules.denominator_variants, rules.numerator_statuses |
| C04 | SYSTEM_RTC | Meaning is not defined in the sources beyond 'more likely for non-compliant records'. Modelled as a Bernoulli by COMPLIANCE_STATUS (Non_Compliant 35%, Pending 10%, Compliant 6%, Not_Applicable 4%). | Provisional | rules.system_rtc_prob_by_status |
| C05 | RFB / TOTAL_RFB | Interpretation is not defined in the sources. RFB is a row-level zero-inflated count dependent on COMPLIANCE_STATUS (normally zero when compliant). TOTAL_RFB = sum of RFB over all rows of the same application-month + Poisson 'other findings', repeated on every row of that application-month, hence TOTAL_RFB >= RFB. 1% of each column is null. | Provisional | rules.rfb, rules.total_rfb_extra, missingness.RFB/TOTAL_RFB |
| C06 | RTO_CHANGE_DATE | Entity-level history: 30% of applications have a change before the window; applications whose APPLICATION_RTO band changes get an in-window change date inside the month the band changes; 6% get an in-window date without a band change. A row shows the latest change date on/before its METRIC_DATE, else null (so it is never later than METRIC_DATE). | Provisional | entity.rto_history_pre_window_share, entity.rto_extra_in_window_date_share |
| C07 | Exemptions | EXEMPTION_LEVEL_1 is populated for ~97% of Exempt rows (85% reuse the application's preferred Exemption_NN) and for ~2% of other rows ('usually populated when Exempt; otherwise often blank'). | Provisional | missingness.EXEMPTION_* |

## Risk-code and tier interpretation

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| D01 | Tier & risk direction | APPLICATION_TIER (1-4), APPLICATION_RTO bands and the P/A/C/I risk codes are generated from a shared latent factor so that they co-move NUMERICALLY (a higher code tends to accompany higher codes elsewhere). The sources do not say whether tier 1 or tier 4, or P1 or P4, is more critical/severe, and no severity direction is asserted or implied. | Provisional (no severity semantics) | entity.latent_loading |
| D02 | Risk codes | ASSET_RISK_RATING_2 (P1-P4) is approximately the rounded mean of the three ARR component codes plus noise. That is a generator device to look coherent, not a client formula; the consuming team defines the real meaning. | Provisional | entity.p_code_noise_sd |
| D03 | Risk vs compliance | Risk attributes are generated independently of the compliance scenario, so high-risk applications are not systematically non-compliant and failed tests occur across all risk codes. The validation step checks that no risk code is all/none non-compliant. | Provisional | - |

## Organisational hierarchy, legal entity, owners

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| E01 | Organisation | Two independent four-level hierarchies. Each hierarchy-2 department rolls up to exactly one hierarchy-1 (BU_) department via a fixed mapping. ORG_GROUP_TYPE is DEPARTMENT for 88% of applications (both department columns populated) and SUPER_DEPARTMENT for 12% (both department columns null). BUS_ORG_LG_NM is Business_Org_ + the suffix of the department (or super-department). | Provisional | cardinality.org1/org2, entity.super_department_level_rate |
| E02 | Cost centres | Each cost centre belongs to exactly one department; an application's cost centre always belongs to its department. A reorganisation moves an application to a new department, hierarchy path and cost centre together. | Provisional | cardinality.n_cost_centers, change_rates.reorg/cost_center |
| E03 | Legal entities | Legal entities carry the three bank-grouping flags (12% belong to none, giving a null USBANKS_LE_LIST). Applications choose legal entities with a division-specific Zipf mix. | Provisional | entity.legal_entity_no_bank_rate |
| E04 | Owners & locations | Owners are fictional people (unique first+last pair) pooled per super-division and drawn Zipf-weighted. EMPLOYEE_BUILDING_NAME is the business owner's building (person attribute) and EMPLOYEE_COUNTRY_NAME follows from it. BUILDING_NAME follows the owner's building 60% of the time. EVENT_LOCATION is a fixed function of BUILDING_NAME. | Provisional | zipf.owner, entity.building_follow_owner_prob |

## Entity stability

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| F01 | Stability | Each controlled-change group (tier, RTO band, lifecycle, risk codes, business owner, IT owner, reorganisation, cost centre, legal entity, building) changes at most once per application, with the stated per-application probability (1.5%-5%), at a random observed month. Among applications with 2+ rows the OBSERVED change share is close to the configured probability (sampling noise of roughly +/-1 percentage point; a change is only visible if the application has a row at or after the change month, and single-row applications cannot show change at all). APPLICATION_NAME, GRN, EON_ID, M&A fields and the critical-KBS flags never change. | Provisional | change_rates.* |
| F02 | Lifecycle change | A lifecycle change advances one phase (Planning > Development > Implementation > Production > Retirement); Retirement does not change. | Provisional | - |

## Aggregation grain and de-duplication rules

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| G01 | Aggregation rule | Counting applications: COUNT(DISTINCT EON_ID) inside the reporting-month filter. Counting rows is not counting applications (an application can have several metric rows per month). | Documented rule | - |
| G02 | Aggregation rule | Rate-type measures: SUM(IS_NUMERATOR) / SUM(IS_DENOMINATOR) at row grain. Variants A and B have different scopes, so filter or group by METRIC_ID when comparing rates across metrics. | Documented rule (provisional semantics) | - |
| G03 | Aggregation rule | Application-level attributes are stable except for the controlled changes; for a single month use the row values in that month, for multi-month roll-ups take the latest reporting month per EON_ID (deduplicate on EON_ID + REPORTING_MONTHEND_DATE). | Documented rule | - |
| G04 | Aggregation rule | Do not SUM TOTAL_RFB across rows: it repeats for every metric row of the same application-month. Use MAX(TOTAL_RFB) per (EON_ID, REPORTING_MONTHEND_DATE) before aggregating. | Documented rule | - |
| G05 | Aggregation rule | Organisation / legal-entity contributions: report both row counts and distinct-application counts - they differ because of the multi-metric rows. | Documented rule | - |
| G06 | Aggregation rule | Trend demonstrations: use rates or shares (e.g. non-compliant share of rows, provisional compliance rate) rather than absolute row / application counts, because the reporting population grows by construction (B05). The aggregate compliance rate is roughly flat by design; scenario-driven change is visible at application, organisation and legal-entity level. | Documented rule | - |

## Limitations

| ID | Area | Decision / assumption | Status | Config key |
|---|---|---|---|---|
| H01 | Not representable | Because the confidential source data was not available, no claim is made about real-world prevalence of any category, the true metric catalogue, real tier/risk semantics, real RFB semantics or the true hierarchy sizes. | Limitation | - |

## Observed outcomes of the provisional rules (this run)

- Distinct EON_ID: 1,500; distinct METRIC_ID: 24
- Observations per EON_ID: median 6, mean 7.60, max 36
- Applications observed in 2+ periods: 90.7%; in 6+ periods: 51.3%; in all periods: 25.0%
- Scenario shares (entity level): consistently_compliant 31.7%, persistently_noncompliant 16.0%, volatile_mixed 12.2%, no_completed_tests 8.5%, exempt 7.4%, improving_after_remediation 7.1%, pending_tests 6.9%, deteriorating 6.3%, not_applicable_scope 3.9%

These are properties of the generated data only. They are **not** properties of the client's confidential data.
