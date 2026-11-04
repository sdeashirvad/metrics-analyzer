#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_client_dataset.py
==========================
Metrics Analyzer -- privacy-safe SYNTHETIC enterprise application / compliance dataset.

* 100% synthetic. Runs offline. No network, no client data, no real names.
* Deterministic for a given PROFILE_CONFIG + seed (default 20261103).
* Output: 57 columns in the exact order given by the client's specification,
  11,399 data rows by default, CSV + XLSX + validation / profile / assumption reports.

Run:
    python3 generate_client_dataset.py                      # defaults
    python3 generate_client_dataset.py --seed 7 --output-dir out_alt
    python3 generate_client_dataset.py --config overrides.json   # deep-merged over PROFILE_CONFIG

Dependencies: pandas, numpy, openpyxl (reading), xlsxwriter (optional, faster XLSX writing).
scipy / Faker are NOT required (stdlib NormalDist is used for latent-Gaussian discretisation).

Pipeline (all functions below):
    build_config -> build_lookup_tables -> generate_entities -> generate_rows
    -> enforce_rules -> save_outputs -> (reload CSV + XLSX) -> validate_data (+ disclosure_scan)
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from statistics import NormalDist

import numpy as np
import pandas as pd

GENERATOR_VERSION = "1.0.0"

# --------------------------------------------------------------------------------------
# Contract constants (from the client specification; NOT configuration)
# --------------------------------------------------------------------------------------
CONTRACT_ROWS = 11399
CONTRACT_COLS = 57
CONTRACT_SEED = 20261103

EXPECTED_COLUMNS = [
    "METRIC_ID", "METRIC_DATE", "METRIC_DATE_TYPE", "IS_NUMERATOR", "IS_DENOMINATOR", "EON_ID",
    "BUILDING_NAME", "EVENT_LOCATION", "APPLICATION_TIER", "EXEMPTION_LEVEL_1", "TEST_STATUS",
    "TEST_RESULT", "SYSTEM_RTC", "RFB", "TOTAL_RFB", "COMPLIANCE_STATUS", "COMPLIANCE_REASON",
    "RTO_CHANGE_DATE", "GRN", "APPLICATION_NAME", "APPLICATION_RTO", "HAS_CTIRICAL_KBS",
    "LIFECYCLE_PHASE", "ASSET_RISK_RATING_2", "ARR_AVAILABILITY", "ARR_CONFIDENTIALITY",
    "ARR_INTEGRITY", "IS_MERGERS_ACQUISITIONS_ASSET", "ACQUIRED_ENTITY", "BU_SUPER_DIVISION",
    "BU_DIVISION", "BU_SUPER_DEPARTMENT", "BU_DEPARTMENT", "ORG_GROUP_TYPE", "SUPER_DIVISION",
    "DIVISION", "SUPER_DEPARTMENT", "DEPARTMENT", "BUS_ORG_LG_NM", "COST_CENTER_CODE",
    "COST_CENTER_NAME", "EMPLOYEE_BUILDING_NAME", "EMPLOYEE_COUNTRY_NAME", "PRIMARY_BUS_FIRST_NAME",
    "PRIMARY_BUS_LAST_NAME", "PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME", "LEGAL_ENTITY_CODE",
    "LEGAL_ENTITY_NAME", "IS_USBANKS", "IS_MSBNA", "IS_MSPBNA", "USBANKS_LE_LIST", "KBS_FLAG_FLAG",
    "REPORTING_MONTHEND_DATE", "REPORTING_MONTH", "REPORTING_YEAR",
]
DATE_COLS = ["METRIC_DATE", "RTO_CHANGE_DATE", "REPORTING_MONTHEND_DATE"]
INT_COLS = ["IS_NUMERATOR", "IS_DENOMINATOR", "APPLICATION_TIER", "SYSTEM_RTC", "RFB", "TOTAL_RFB",
            "REPORTING_MONTH", "REPORTING_YEAR"]
# Columns the dictionary / specification allows to be null (everything else must be populated).
NULLABLE_COLS = ["EXEMPTION_LEVEL_1", "TEST_RESULT", "RFB", "TOTAL_RFB", "RTO_CHANGE_DATE",
                 "BU_DEPARTMENT", "DEPARTMENT", "USBANKS_LE_LIST"]
YN_COLS = ["HAS_CTIRICAL_KBS", "IS_MERGERS_ACQUISITIONS_ASSET", "IS_USBANKS", "IS_MSBNA", "IS_MSPBNA",
           "KBS_FLAG_FLAG"]
STRING_NULL_TOKENS = {"NULL", "null", "None", "none", "NaN", "nan", "N/A", "n/a", "NA", "<NA>", "", " "}

LIFECYCLE_ORDER = ["Planning", "Development", "Implementation", "Production", "Retirement"]
BANK_LABELS = ["BANK_A", "BANK_B", "BANK_C"]  # IS_USBANKS -> A, IS_MSBNA -> B, IS_MSPBNA -> C
BANK_FLAG_COLS = ["IS_USBANKS", "IS_MSBNA", "IS_MSPBNA"]
TEST_STATUSES = ["Test_Complete", "No_Test", "Test_Pending", "Exempt"]
COMPLIANCE_STATUSES = ["Compliant", "Non_Compliant", "Not_Applicable", "Pending"]

# --------------------------------------------------------------------------------------
# PROFILE_CONFIG -- every tunable lives here. Probability vectors are re-normalised on load.
# --------------------------------------------------------------------------------------
PROFILE_CONFIG = {
    "row_count": CONTRACT_ROWS,
    "seed": CONTRACT_SEED,
    "output_dir": "client_dataset_output",
    "files": {
        "csv": "synthetic_enterprise_data.csv",
        "xlsx": "synthetic_enterprise_data.xlsx",
        "validation_report": "validation_report.md",
        "profile": "data_profile.json",
        "assumptions": "assumptions_register.md",
        "golden_questions": "golden_questions.md",
        "metadata_dir": "metadata",
    },
    # Path to the client's data dictionary. None => auto-detect next to this script.
    "source_dictionary_path": None,

    # ---- Reporting calendar --------------------------------------------------------
    "reporting": {
        "end_date": "2026-10-31",          # last month-end (rolled forward to month-end if needed)
        "n_months": 12,                    # consecutive month-end periods
        "date_type_labels": ["Monthend"],  # METRIC_DATE_TYPE vocabulary
        "date_type_probs": [1.0],
    },

    # ---- Cardinalities -------------------------------------------------------------
    "cardinality": {
        "n_entities": 1500,                # distinct EON_ID
        "n_metrics": 24,                   # distinct METRIC_ID
        "n_metric_families": 6,
        "n_buildings": 45,
        "n_locations": 32,
        "n_countries": 8,
        "n_cost_centers": 320,
        "n_legal_entities": 40,
        "n_business_owners": 600,
        "n_it_owners": 450,
        "n_exemption_levels": 12,
        "n_acquired_entities": 8,
        # hierarchy shape: [min, max] children per parent (uniform integer)
        "org2": {"n_super_divisions": 8, "divisions": [2, 4], "super_departments": [2, 4], "departments": [2, 4]},
        "org1": {"n_super_divisions": 6, "divisions": [2, 3], "super_departments": [2, 3], "departments": [2, 3]},
    },

    # ---- Synthetic identifier formats (ranges deliberately unrelated to any real numbering) -----
    "id_prefixes": {"eon": "EON", "metric": "M", "cost_center": "CC", "legal_entity": "LE"},
    "id_ranges": {"eon": [610000, 989999], "metric": [310000, 389999],
                  "cost_center": [41000, 48999], "legal_entity": [2000, 4999]},

    # ---- Heavy-tail (Zipf) exponents (larger => more concentrated) --------------------
    "zipf": {"metric": 0.8, "org_leaf": 0.7, "building": 0.8, "legal_entity": 0.9, "owner": 0.85,
             "cost_center_extra": 0.7, "exemption_level": 1.1, "acquired_entity": 0.8,
             "super_division": 0.6, "country": 0.9},

    # ---- Observation plan (how the fixed row budget is spread over entity x metric x month) ----
    "observations": {
        "lognormal_sigma": 1.0,                      # spread of observations-per-entity
        "metrics_per_entity_probs": [0.72, 0.22, 0.06],   # share of entities with 1, 2, 3 metrics
        "metric_split_weights": [0.60, 0.25, 0.15],
        "same_family_prob": 0.70,                    # secondary metrics prefer the primary's family
        "gap_probs": [0.55, 0.25, 0.12, 0.08],       # extra window months beyond observed count (0..3)
        "anchor_probs": {"end": 0.50, "start": 0.15, "random": 0.35},  # window anchoring
        "metric_variant_b_share": 0.40,              # share of metrics using denominator variant B
        "metric_nc_offset_sd": 0.35,                 # metric-level logit shift on failure probability
    },

    # ---- Entity (application) attribute marginals --------------------------------------
    "entity": {
        "application_tier": [0.10, 0.30, 0.38, 0.22],             # tiers 1..4
        "application_rto_labels": ["RTO_0_1H", "RTO_1_4H", "RTO_4_12H", "RTO_12_24H", "RTO_24_72H", "RTO_GT_72H"],
        "application_rto_probs": [0.06, 0.18, 0.26, 0.24, 0.18, 0.08],
        "lifecycle_labels": ["Production", "Implementation", "Development", "Retirement", "Planning"],
        "lifecycle_probs": [0.64, 0.09, 0.11, 0.09, 0.07],
        "arr_probs": {"A": [0.18, 0.32, 0.32, 0.18], "C": [0.12, 0.28, 0.36, 0.24], "I": [0.20, 0.34, 0.30, 0.16]},
        "latent_loading": {"tier": 0.55, "rto": 0.40, "arr": 0.50},    # numeric co-movement only
        "p_code_noise_sd": 0.45,
        "critical_kbs_base_rate": 0.22,
        "critical_kbs_loading": 0.80,
        "kbs_flag_disagreement_rate": 0.0,        # KBS_FLAG_FLAG vs HAS_CTIRICAL_KBS (0 => identical)
        "ma_rate": 0.08,
        "super_department_level_rate": 0.12,       # ORG_GROUP_TYPE = SUPER_DEPARTMENT share
        "bank_flag_rates": [0.55, 0.30, 0.15],     # legal-entity level P(IS_USBANKS, IS_MSBNA, IS_MSPBNA = Y)
        "legal_entity_no_bank_rate": 0.12,         # legal entities in none of the groupings (list => null)
        "building_follow_owner_prob": 0.60,
        "owner_home_building_prob": 0.70,
        "home_buildings_per_super_division": 5,
        "n_countries_used_by_buildings": 8,
        "owner_same_division_pool_prob": 1.0,
        "rto_history_pre_window_share": 0.30,      # entities with an RTO change before the window
        "rto_extra_in_window_date_share": 0.06,    # in-window RTO_CHANGE_DATE updates without band change
        "exemption_entity_level_prob": 0.85,       # exempt rows reuse the entity's exemption level
    },

    # ---- Stability: P(an attribute group changes once during the window), per entity -----
    "change_rates": {
        "tier": 0.03, "rto": 0.04, "lifecycle": 0.05, "risk": 0.03, "bus_owner": 0.03,
        "it_owner": 0.03, "reorg": 0.02, "cost_center": 0.02, "legal_entity": 0.015, "building": 0.02,
    },

    # ---- Scenarios (documented behavioural archetypes) ---------------------------------
    "scenarios": {
        "fractions": {
            "consistently_compliant": 0.30, "persistently_noncompliant": 0.12, "deteriorating": 0.10,
            "improving_after_remediation": 0.10, "volatile_mixed": 0.14, "no_completed_tests": 0.07,
            "pending_tests": 0.07, "exempt": 0.06, "not_applicable_scope": 0.04,
        },
        "min_span_months": {"deteriorating": 5, "improving_after_remediation": 5, "volatile_mixed": 3},
        "switch_quantile_range": [0.35, 0.65],
        # TEST_STATUS probabilities [Test_Complete, No_Test, Test_Pending, Exempt]
        "test_status_probs": {
            "consistently_compliant": [0.90, 0.04, 0.04, 0.02],
            "persistently_noncompliant": [0.80, 0.12, 0.06, 0.02],
            "deteriorating": [0.85, 0.07, 0.06, 0.02],
            "improving_after_remediation": [0.85, 0.07, 0.06, 0.02],
            "volatile_mixed": [0.80, 0.08, 0.10, 0.02],
            "no_completed_tests": [0.00, 0.88, 0.05, 0.07],
            "pending_tests": [0.04, 0.06, 0.86, 0.04],
            "exempt": [0.03, 0.05, 0.04, 0.88],
            "not_applicable_scope": [0.03, 0.90, 0.02, 0.05],
        },
        # P(test fails | Test_Complete): linear ramp start -> end around the entity switch month
        "p_fail": {
            "consistently_compliant": {"start": 0.05, "end": 0.05},
            "persistently_noncompliant": {"start": 0.88, "end": 0.88},
            "deteriorating": {"start": 0.06, "end": 0.85},
            "improving_after_remediation": {"start": 0.85, "end": 0.06},
            "volatile_mixed": {"uniform": [0.25, 0.65]},
            "no_completed_tests": {"start": 0.35, "end": 0.35},
            "pending_tests": {"start": 0.35, "end": 0.35},
            "exempt": {"start": 0.35, "end": 0.35},
            "not_applicable_scope": {"start": 0.35, "end": 0.35},
        },
        "ramp_months": 2.0,
        "rfb_scale": {"persistently_noncompliant": 1.8, "deteriorating": 1.2, "volatile_mixed": 1.1},
    },

    # ---- Joint compliance / test rule tables (PROVISIONAL -- see assumptions register) ----
    "rules": {
        "compliance_given_test": {
            "TC|Pass": {"Compliant": 0.92, "Non_Compliant": 0.05, "Pending": 0.03},
            "TC|Fail": {"Non_Compliant": 0.88, "Compliant": 0.07, "Pending": 0.05},
            "TC|None": {"Pending": 0.60, "Non_Compliant": 0.25, "Compliant": 0.15},
            "NT|default": {"Pending": 0.45, "Non_Compliant": 0.30, "Not_Applicable": 0.25},
            "NT|no_completed_tests": {"Pending": 0.35, "Non_Compliant": 0.45, "Not_Applicable": 0.20},
            "NT|not_applicable_scope": {"Not_Applicable": 0.75, "Pending": 0.15, "Non_Compliant": 0.10},
            "TP|any": {"Pending": 0.88, "Non_Compliant": 0.12},
            "EX|any": {"Not_Applicable": 0.80, "Compliant": 0.12, "Non_Compliant": 0.08},
        },
        # key = COMPLIANCE_STATUS|TEST_STATUS|TEST_RESULT ('None' = null result)
        "reason_table": {
            "Compliant|Test_Complete|Pass": {"Requirements_Met": 0.70, "Controls_Verified": 0.20, "Remediation_Verified": 0.10},
            "Compliant|Test_Complete|Fail": {"Compensating_Control_Accepted": 0.60, "Remediation_Verified": 0.40},
            "Compliant|Test_Complete|None": {"Requirements_Met": 1.0},
            "Compliant|Exempt|None": {"Exemption_Conditions_Met": 1.0},
            "Non_Compliant|Test_Complete|Pass": {"Open_Findings_Outstanding": 1.0},
            "Non_Compliant|Test_Complete|Fail": {"Test_Failed": 0.50, "Open_Findings_Outstanding": 0.30, "Remediation_Overdue": 0.20},
            "Non_Compliant|Test_Complete|None": {"Open_Findings_Outstanding": 1.0},
            "Non_Compliant|No_Test|None": {"No_Test_Performed": 0.65, "Test_Overdue": 0.35},
            "Non_Compliant|Test_Pending|None": {"Test_Overdue": 1.0},
            "Non_Compliant|Exempt|None": {"Exemption_Expired": 1.0},
            "Pending|Test_Complete|Pass": {"Result_Under_Review": 1.0},
            "Pending|Test_Complete|Fail": {"Remediation_In_Progress": 1.0},
            "Pending|Test_Complete|None": {"Result_Under_Review": 1.0},
            "Pending|Test_Pending|None": {"Test_Scheduled": 0.50, "Test_In_Progress": 0.50},
            "Pending|No_Test|None": {"Awaiting_Test_Assignment": 1.0},
            "Not_Applicable|No_Test|None": {"No_Test_Required": 1.0},
            "Not_Applicable|Exempt|None": {"Exemption_Approved": 1.0},
        },
        # improving-after-remediation scenario, post-switch Compliant|Test_Complete|Pass reasons
        "improving_post_switch_reasons": {"Remediation_Verified": 0.50, "Requirements_Met": 0.35, "Controls_Verified": 0.15},
        "system_rtc_prob_by_status": {"Compliant": 0.06, "Non_Compliant": 0.35, "Pending": 0.10, "Not_Applicable": 0.04},
        # RFB: P(zero), Poisson lambda for (RFB-1) when non-zero
        "rfb": {
            "Compliant": {"p_zero": 0.92, "lam": 0.15},
            "Non_Compliant": {"p_zero": 0.10, "lam": 1.60},
            "Pending": {"p_zero": 0.85, "lam": 0.30},
            "Not_Applicable": {"p_zero": 0.97, "lam": 0.10},
        },
        "total_rfb_extra": {"base_lambda": 0.20, "per_failure_prob": 2.0},   # entity-month 'other findings'
        # Denominator variants: A = Compliant + Non_Compliant; B = every status except Not_Applicable
        "denominator_variants": {"A": ["Compliant", "Non_Compliant"],
                                 "B": ["Compliant", "Non_Compliant", "Pending"]},
        "numerator_statuses": ["Compliant"],
    },

    # ---- Missingness (column-specific; conditional rules live in the rule tables) -------
    "missingness": {
        "RFB": 0.010,
        "TOTAL_RFB": 0.010,
        "TEST_RESULT_when_test_complete": 0.008,
        "EXEMPTION_LEVEL_1_when_exempt": 0.030,
        "EXEMPTION_LEVEL_1_populated_when_not_exempt": 0.020,
    },

    # ---- Validation thresholds ---------------------------------------------------------
    "validation": {
        "min_distinct_entities": 1000, "max_distinct_entities": 2000,
        "min_share_entities_2plus_months": 0.70,
        "min_share_entities_6plus_months": 0.40,
        "max_entity_share_with_attribute_change": 0.10,
        "extra_forbidden_terms": [],     # extend the disclosure deny-list here
    },
}

# --------------------------------------------------------------------------------------
# Disclosure deny-lists (extend via PROFILE_CONFIG['validation']['extra_forbidden_terms'])
# Single lower-case tokens are matched against whole tokens in every string VALUE.
# (Column NAMES keep the client's legacy spelling and are intentionally not scanned.)
# --------------------------------------------------------------------------------------
FORBIDDEN_TERMS = {
    # banks / financial firms / well-known corporate brands
    "jpmorgan", "jpmc", "citibank", "citigroup", "citi", "wells", "fargo", "goldman", "sachs", "morgan",
    "stanley", "barclays", "hsbc", "ubs", "deutsche", "santander", "bnp", "paribas", "nomura", "lazard",
    "blackrock", "vanguard", "schwab", "fidelity", "amex", "mastercard", "paypal", "pnc", "truist",
    "merrill", "lynch", "mufg", "mizuho", "rbc", "scotiabank", "bmo", "usbank", "usbancorp", "keybank",
    "microsoft", "oracle", "salesforce", "amazon", "google", "ibm", "cisco", "vmware", "servicenow",
    "workday", "adobe", "sap", "sybase", "teradata", "snowflake", "splunk",
}
FORBIDDEN_SUBSTRINGS = ["usbanks", "msbna", "mspbna", "morganstanley", "jpmorgan", "goldmansachs",
                        "wellsfargo", "bankofamerica", "@", "http://", "https://", "www."]
REAL_FIRST_NAMES = set("""james john robert michael william david richard joseph thomas charles mary patricia
jennifer linda elizabeth barbara susan jessica sarah karen daniel matthew anthony mark paul steven andrew
kenneth joshua kevin brian george edward ronald timothy jason jeffrey ryan jacob gary nicholas eric jonathan
stephen larry justin scott brandon benjamin samuel gregory frank alexander raymond patrick jack dennis jerry
tyler aaron nancy lisa betty margaret sandra ashley kimberly emily donna michelle carol amanda melissa
deborah stephanie rebecca laura sharon cynthia kathleen amy angela shirley anna brenda pamela emma nicole
helen samantha katherine christine debra rachel catherine carolyn janet ruth maria heather diane virginia
julie joyce victoria olivia kelly christina lauren joan evelyn judith megan cheryl andrea hannah martha
jacqueline frances gloria ann teresa kathryn sara janice jean alice madison doris abigail julia judy grace
denise amber marilyn beverly danielle theresa sophia marie diana brittany natalie isabella charlotte rose
alexis kayla wei raj priya amit arjun ravi anil sunil vikram neha pooja rahul sanjay deepak ankit mohammed
ahmed ali omar fatima yusuf carlos jose juan luis miguel pedro sofia lucia elena ivan sergei olga""".split())
REAL_LAST_NAMES = set("""smith johnson williams brown jones garcia miller davis rodriguez martinez hernandez
lopez gonzalez wilson anderson thomas taylor moore jackson martin lee perez thompson white harris sanchez
clark ramirez lewis robinson walker young allen king wright scott torres nguyen hill flores green adams
nelson baker hall rivera campbell mitchell carter roberts patel shah kumar singh chen wang zhang kim park
gupta sharma reddy khan ali ahmed hussain cohen levy schmidt schneider fischer weber meyer wagner becker
rossi russo ferrari esposito bianchi romano colombo ricci marino greco silva santos oliveira souza costa
ivanov petrov smirnov kuznetsov popov tanaka suzuki sato takahashi watanabe ito yamamoto nakamura""".split())

# Name syllable inventories (internal; fictional)
_FN_ON = ["Qu", "Zen", "Vor", "Lia", "Mar", "Tel", "Bri", "Kav", "Ixo", "Nur", "Sel", "Dro", "Fen", "Yal", "Pim",
          "Ghe", "Tho", "Wyn", "Ula", "Cor", "Jav", "Hel", "Oro", "Eld", "Sav", "Rin", "Bex", "Nol", "Pyr", "Zul"]
_FN_MID = ["ve", "ni", "ta", "lo", "ri", "so", "mu", "ka", "de", "fi", "zu", "an", "el", "or"]
_FN_END = ["n", "ta", "na", "ro", "k", "xa", "la", "m", "th", "s", "ve", "dra", "ni", "x"]
_LN_ON = ["Len", "Wra", "Kos", "Bel", "Tur", "Hax", "Mir", "Gal", "Pov", "Dun", "Fal", "Yor", "Ziv", "Quo", "Rha",
          "Sib", "Tov", "Ulm", "Cra", "Dex", "Ond", "Vip", "Jor", "Nev"]
_LN_MID = ["a", "e", "o", "i", "u", "ar", "en", "ol"]
_LN_END = ["wr", "ha", "ven", "dak", "mir", "loc", "shaw", "pek", "rin", "tov", "quin", "bar", "zel", "mos"]


# ======================================================================================
# Generic helpers
# ======================================================================================
def stage_rng(cfg: dict, stage: int) -> np.random.Generator:
    """Independent, reproducible RNG stream per generation stage."""
    return np.random.default_rng(np.random.SeedSequence([int(cfg["seed"]), int(stage)]))


def zipf_weights(rng, n: int, s: float, shuffle: bool = True) -> np.ndarray:
    w = 1.0 / np.arange(1, n + 1, dtype=float) ** s
    if shuffle:
        w = w[rng.permutation(n)]
    return w / w.sum()


def norm_probs(p) -> np.ndarray:
    a = np.asarray(p, dtype=float)
    if (a < 0).any() or a.sum() <= 0:
        raise ValueError(f"invalid probability vector: {p}")
    return a / a.sum()


def digitize_normal(x: np.ndarray, probs) -> np.ndarray:
    """Map standard-normal draws to categories 0..k-1 with exact marginal `probs`."""
    nd = NormalDist()
    cum = np.cumsum(norm_probs(probs))[:-1]
    th = np.array([nd.inv_cdf(min(max(c, 1e-9), 1 - 1e-9)) for c in cum])
    return np.searchsorted(th, x)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def deep_update(base: dict, upd: dict) -> dict:
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def sample_categorical(rng, keys: np.ndarray, table: dict) -> np.ndarray:
    """For each row draw a label from table[key] (dict label->prob). Deterministic key order."""
    out = np.empty(len(keys), dtype=object)
    for key in sorted(set(keys.tolist())):
        idx = np.flatnonzero(keys == key)
        labels = list(table[key].keys())
        p = norm_probs(list(table[key].values()))
        out[idx] = rng.choice(np.array(labels, dtype=object), size=len(idx), p=p)
    return out


def to_py(o):
    if isinstance(o, dict):
        return {str(k): to_py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_py(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return pd.Timestamp(o).strftime("%Y-%m-%d")
    if o is pd.NA or (isinstance(o, float) and math.isnan(o)):
        return None
    return o


# ======================================================================================
# 1. build_config
# ======================================================================================
def build_config(overrides: dict | None = None, config_path: str | None = None) -> dict:
    cfg = copy.deepcopy(PROFILE_CONFIG)
    if config_path:
        with open(config_path, "r", encoding="utf-8") as fh:
            deep_update(cfg, json.load(fh))
    if overrides:
        deep_update(cfg, overrides)

    # sanity: probability vectors & fractions
    sc = cfg["scenarios"]
    names = list(sc["fractions"].keys())
    for k in ("test_status_probs", "p_fail"):
        missing = [n for n in names if n not in sc[k]]
        if missing:
            raise ValueError(f"scenarios.{k} missing entries for {missing}")
    fr = norm_probs(list(sc["fractions"].values()))
    sc["fractions"] = {n: float(f) for n, f in zip(names, fr)}
    for n in names:
        if len(sc["test_status_probs"][n]) != 4:
            raise ValueError("test_status_probs need 4 entries [Test_Complete, No_Test, Test_Pending, Exempt]")
    ent = cfg["entity"]
    for k, n in (("application_tier", 4), ("application_rto_probs", len(ent["application_rto_labels"])),
                 ("lifecycle_probs", len(ent["lifecycle_labels"]))):
        if len(ent[k]) != n:
            raise ValueError(f"entity.{k} must have {n} entries")
    for lab in ent["lifecycle_labels"]:
        if lab not in LIFECYCLE_ORDER:
            raise ValueError(f"unknown lifecycle label {lab}")
    c = cfg["cardinality"]
    if cfg["row_count"] < c["n_entities"]:
        raise ValueError("row_count must be >= n_entities (every entity needs >= 1 observation)")
    if c["n_buildings"] < c["n_locations"]:
        raise ValueError("n_buildings must be >= n_locations")
    for key in ("n_exemption_levels", "n_acquired_entities", "n_legal_entities", "n_countries", "n_buildings"):
        if c[key] > 99 and key != "n_buildings":
            raise ValueError(f"{key} must be < 100 (2-digit labels)")
    if cfg["row_count"] > cfg["reporting"]["n_months"] * c["n_entities"] * 3:
        raise ValueError("row_count exceeds entity x metric x month capacity")
    return cfg


# ======================================================================================
# 2. build_lookup_tables
# ======================================================================================
def _month_ends(cfg) -> pd.DatetimeIndex:
    r = cfg["reporting"]
    end = pd.Timestamp(r["end_date"]) + pd.offsets.MonthEnd(0)
    ends = [end - pd.offsets.MonthEnd(i) for i in range(r["n_months"] - 1, -1, -1)]
    return pd.DatetimeIndex(ends).normalize()


def _build_hierarchy(rng, spec: dict, names: dict) -> pd.DataFrame:
    """Deterministic 4-level hierarchy; one row per lowest-level department (leaf)."""
    rows = []
    for a in range(1, spec["n_super_divisions"] + 1):
        for b in range(1, int(rng.integers(spec["divisions"][0], spec["divisions"][1] + 1)) + 1):
            for c in range(1, int(rng.integers(spec["super_departments"][0], spec["super_departments"][1] + 1)) + 1):
                for d in range(1, int(rng.integers(spec["departments"][0], spec["departments"][1] + 1)) + 1):
                    rows.append((a, b, c, d))
    df = pd.DataFrame(rows, columns=["a", "b", "c", "d"])
    df["sd_idx"] = df["a"] - 1
    df["top"] = [f"{names['top']}_{a:02d}" for a in df.a]
    df["div"] = [f"{names['div']}_{a:02d}_{b:02d}" for a, b in zip(df.a, df.b)]
    df["sdp"] = [f"{names['sdp']}_{a:02d}_{b:02d}_{c:02d}" for a, b, c in zip(df.a, df.b, df.c)]
    df["dep"] = [f"{names['dep']}_{a:02d}_{b:02d}_{c:02d}_{d:02d}" for a, b, c, d in zip(df.a, df.b, df.c, df.d)]
    if names.get("bus"):
        df["bus_dep"] = [f"{names['bus']}_{a:02d}_{b:02d}_{c:02d}_{d:02d}" for a, b, c, d in zip(df.a, df.b, df.c, df.d)]
        df["bus_sdp"] = [f"{names['bus']}_{a:02d}_{b:02d}_{c:02d}" for a, b, c in zip(df.a, df.b, df.c)]
    return df


def _make_people(rng, n: int, used: set, kind: str) -> list:
    """Fictional (first,last) pairs from syllable lists; rejects deny-listed real names."""
    out = []
    guard = 0
    while len(out) < n:
        guard += 1
        if guard > n * 200:
            raise RuntimeError("could not generate enough unique synthetic names")
        first = (_FN_ON[rng.integers(len(_FN_ON))] + _FN_MID[rng.integers(len(_FN_MID))] + _FN_END[rng.integers(len(_FN_END))])
        last = (_LN_ON[rng.integers(len(_LN_ON))] + _LN_MID[rng.integers(len(_LN_MID))] + _LN_END[rng.integers(len(_LN_END))])
        if first.lower() in REAL_FIRST_NAMES or last.lower() in REAL_LAST_NAMES:
            continue
        if first.lower() in FORBIDDEN_TERMS or last.lower() in FORBIDDEN_TERMS:
            continue
        if (first, last) in used:
            continue
        used.add((first, last))
        out.append((first, last))
    return out


def build_lookup_tables(cfg: dict) -> dict:
    """Latent lookup tables reused for every one of the observations."""
    rng = stage_rng(cfg, 1)
    C, Z = cfg["cardinality"], cfg["zipf"]
    E = cfg["entity"]
    L: dict = {}

    # --- reporting calendar ---------------------------------------------------------
    me = _month_ends(cfg)
    L["month_ends"] = me
    L["n_months"] = len(me)
    L["calendar"] = pd.DataFrame({"t": np.arange(len(me)), "REPORTING_MONTHEND_DATE": me,
                                  "REPORTING_MONTH": me.month, "REPORTING_YEAR": me.year})

    # --- buildings / locations / countries (linked) -----------------------------------
    nb, nl, nc = C["n_buildings"], C["n_locations"], C["n_countries"]
    b_ids = np.arange(1, nb + 1)
    cw = zipf_weights(rng, nc, Z["country"])
    L["buildings"] = pd.DataFrame({
        "building": [f"Building_{i:03d}" for i in b_ids],
        "location": [f"Location_{((i - 1) % nl) + 1:03d}" for i in b_ids],   # deterministic building -> location
        "country": [f"Country_{k + 1:02d}" for k in rng.choice(nc, size=nb, p=cw)],
    })

    # --- organisational hierarchies -----------------------------------------------------
    org2 = _build_hierarchy(rng, C["org2"], {"top": "Super_Division", "div": "Division", "sdp": "Super_Department",
                                             "dep": "Department", "bus": "Business_Org"})
    org1 = _build_hierarchy(rng, C["org1"], {"top": "BU_Super_Division", "div": "BU_Division",
                                             "sdp": "BU_Super_Department", "dep": "BU_Department"})
    L["org2"], L["org1"] = org2, org1
    # every second-hierarchy department rolls up to exactly one first-hierarchy department (deterministic)
    w1 = zipf_weights(rng, len(org1), 0.6)
    L["org2_to_org1"] = rng.choice(len(org1), size=len(org2), p=w1)
    L["n_super_divisions"] = C["org2"]["n_super_divisions"]

    # --- cost centres (code <-> name 1:1, each attached to a department) -----------------
    ncc = C["n_cost_centers"]
    n_leaf = len(org2)
    if ncc < n_leaf:
        raise ValueError("n_cost_centers must be >= number of departments")
    extra = rng.choice(n_leaf, size=ncc - n_leaf, p=zipf_weights(rng, n_leaf, Z["cost_center_extra"]))
    leaf_of_cc = np.sort(np.concatenate([np.arange(n_leaf), extra]))
    lo, hi = cfg["id_ranges"]["cost_center"]
    codes = np.sort(rng.choice(np.arange(lo, hi + 1), size=ncc, replace=False))
    codes = codes[rng.permutation(ncc)]
    pre = cfg["id_prefixes"]["cost_center"]
    L["cost_centers"] = pd.DataFrame({
        "code": [f"{pre}{c}" for c in codes],
        "name": [f"Cost_Center_{i + 1:03d}" for i in range(ncc)],
        "leaf": leaf_of_cc,
    })
    cnt = np.bincount(leaf_of_cc, minlength=n_leaf)
    L["cc_start"] = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    L["cc_count"] = cnt

    # --- legal entities (code <-> name 1:1; bank-grouping flags are a function of the entity) ----
    nle = C["n_legal_entities"]
    lo, hi = cfg["id_ranges"]["legal_entity"]
    lcodes = rng.choice(np.arange(lo, hi + 1), size=nle, replace=False)
    pre = cfg["id_prefixes"]["legal_entity"]
    rates = np.asarray(E["bank_flag_rates"], float)
    flags = np.zeros((nle, 3), dtype=int)
    for i in range(nle):
        if rng.random() < E["legal_entity_no_bank_rate"]:
            continue
        while flags[i].sum() == 0:
            flags[i] = (rng.random(3) < rates).astype(int)
    L["legal_entities"] = pd.DataFrame({
        "code": [f"{pre}{c}" for c in lcodes],
        "name": [f"Legal_Entity_{i + 1:02d}" for i in range(nle)],
        "IS_USBANKS": np.where(flags[:, 0] == 1, "Y", "N"),
        "IS_MSBNA": np.where(flags[:, 1] == 1, "Y", "N"),
        "IS_MSPBNA": np.where(flags[:, 2] == 1, "Y", "N"),
        "list": ["|".join(b for b, f in zip(BANK_LABELS, row) if f) or None for row in flags],
    })
    # super-division specific legal-entity weights (so LE mix differs by division)
    L["le_weights"] = np.vstack([zipf_weights(rng, nle, Z["legal_entity"]) for _ in range(L["n_super_divisions"])])

    # --- fictional people (stable first/last pairs) & division-specific owner pools ----------
    used: set = set()
    nsd = L["n_super_divisions"]
    sdw = zipf_weights(rng, nsd, Z["super_division"], shuffle=False)
    homes = {sd: rng.choice(nb, size=min(E["home_buildings_per_super_division"], nb), replace=False) for sd in range(nsd)}
    bw = zipf_weights(rng, nb, Z["building"])
    L["building_weights"] = bw

    def build_pool(n_people):
        pairs = _make_people(rng, n_people, used, "p")
        sd_of = rng.choice(nsd, size=n_people, p=sdw)
        # guarantee every super-division owns at least 3 people
        for sd in range(nsd):
            if (sd_of == sd).sum() < 3:
                sd_of[rng.choice(n_people, size=3, replace=False)] = sd
        bld = np.array([rng.choice(homes[s]) if rng.random() < E["owner_home_building_prob"]
                        else rng.choice(nb, p=bw) for s in sd_of])
        people = pd.DataFrame({"first": [p[0] for p in pairs], "last": [p[1] for p in pairs],
                               "sd_idx": sd_of, "building_idx": bld})
        pools, wts = [], []
        for sd in range(nsd):
            ids = np.flatnonzero(sd_of == sd)
            pools.append(ids)
            wts.append(zipf_weights(rng, len(ids), Z["owner"]))
        return people, pools, wts

    L["bus_people"], L["bus_pools"], L["bus_pool_w"] = build_pool(C["n_business_owners"])
    L["it_people"], L["it_pools"], L["it_pool_w"] = build_pool(C["n_it_owners"])

    # --- metric catalogue --------------------------------------------------------------------
    M = C["n_metrics"]
    lo, hi = cfg["id_ranges"]["metric"]
    mnums = np.sort(rng.choice(np.arange(lo, hi + 1), size=M, replace=False))
    nfam = C["n_metric_families"]
    per = int(math.ceil(M / nfam))
    O = cfg["observations"]
    variant = np.where(rng.random(M) < O["metric_variant_b_share"], "B", "A")
    L["metrics"] = pd.DataFrame({
        "METRIC_ID": [f"{cfg['id_prefixes']['metric']}{x}" for x in mnums],
        "family": [f"Metric_Family_{i // per + 1:02d}" for i in range(M)],
        "family_idx": [i // per for i in range(M)],
        "denominator_variant": variant,
        "nc_logit_offset": rng.normal(0.0, O["metric_nc_offset_sd"], size=M),
        "date_type": rng.choice(cfg["reporting"]["date_type_labels"], size=M,
                                p=norm_probs(cfg["reporting"]["date_type_probs"])),
    })
    L["metric_weights"] = zipf_weights(rng, M, Z["metric"])

    # --- exemption / acquired-entity vocabularies -----------------------------------------------
    L["exemption_levels"] = np.array([f"Exemption_{i + 1:02d}" for i in range(C["n_exemption_levels"])], dtype=object)
    L["exemption_weights"] = zipf_weights(rng, C["n_exemption_levels"], Z["exemption_level"])
    L["acquired_entities"] = np.array([f"Acquired_Entity_{i + 1:02d}" for i in range(C["n_acquired_entities"])], dtype=object)
    L["acquired_weights"] = zipf_weights(rng, C["n_acquired_entities"], Z["acquired_entity"])
    L["org_leaf_weights"] = zipf_weights(rng, len(org2), Z["org_leaf"])
    return L


# ======================================================================================
# 3. generate_entities  (application lookup + observation plan)
# ======================================================================================
def _scale_counts(raw: np.ndarray, cap: np.ndarray, total: int, rng) -> np.ndarray:
    """Heavy-tailed observation counts per entity: 1 <= n_e <= cap_e and sum == total."""
    if total < len(raw) or total > cap.sum():
        raise ValueError("row_count infeasible for current cardinalities")
    lo, hi = 1e-3, 1e4
    for _ in range(100):
        k = math.sqrt(lo * hi)
        if np.clip(np.round(raw * k), 1, cap).sum() < total:
            lo = k
        else:
            hi = k
    counts = np.clip(np.round(raw * hi), 1, cap).astype(int)
    diff = total - int(counts.sum())
    while diff != 0:
        if diff > 0:
            cand = np.flatnonzero(counts < cap)
            take = rng.choice(cand, size=min(diff, len(cand)), replace=False)
            counts[take] += 1
            diff -= len(take)
        else:
            cand = np.flatnonzero(counts > 1)
            take = rng.choice(cand, size=min(-diff, len(cand)), replace=False)
            counts[take] -= 1
            diff += len(take)
    return counts


def _split_counts(rng, total: int, n_m: int, weights, cap: int) -> np.ndarray:
    k = np.zeros(n_m, dtype=int)
    base = min(n_m, total)
    k[:base] = 1
    rem = total - base
    w = np.asarray(weights[:n_m], float)
    while rem > 0:
        ww = w * (k < cap)
        j = rng.choice(n_m, p=ww / ww.sum())
        k[j] += 1
        rem -= 1
    return k


def _pick_from_pools(rng, group: np.ndarray, pools, wts) -> np.ndarray:
    """For each row choose a pool member (Zipf-weighted) from the pool of its group."""
    out = np.zeros(len(group), dtype=int)
    for g in np.unique(group):
        idx = np.flatnonzero(group == g)
        out[idx] = rng.choice(pools[g], size=len(idx), p=wts[g])
    return out


def _alt_from_pools(rng, group: np.ndarray, base: np.ndarray, pools) -> np.ndarray:
    """Pick a different pool member than `base` (uniform among the others)."""
    out = base.copy()
    for g in np.unique(group):
        idx = np.flatnonzero(group == g)
        pool = pools[g]
        if len(pool) < 2:
            continue
        pos = np.searchsorted(np.sort(pool), base[idx])           # pools are sorted ascending
        off = rng.integers(1, len(pool), size=len(idx))
        out[idx] = np.sort(pool)[(pos + off) % len(pool)]
    return out


def _change_times(rng, p: float, base, alt, first: np.ndarray, last: np.ndarray, never: int = 99) -> np.ndarray:
    """Month index from which `alt` replaces `base` (never => no change). Visible changes only."""
    has = (rng.random(len(first)) < p) & (np.asarray(base) != np.asarray(alt)) & (last > first)
    t_c = first + 1 + np.floor(rng.random(len(first)) * np.maximum(last - first, 1)).astype(int)
    return np.where(has, t_c, never)


def generate_entities(cfg: dict, L: dict):
    """Create the application (EON_ID) lookup with stable base values, controlled-change alternates,
    behavioural scenarios and the observation plan (entity x metric x month)."""
    rng = stage_rng(cfg, 2)
    C, EN, O, SC = cfg["cardinality"], cfg["entity"], cfg["observations"], cfg["scenarios"]
    Ne, T, M = C["n_entities"], L["n_months"], C["n_metrics"]
    ents = pd.DataFrame({"eidx": np.arange(Ne)})

    # ---- identifiers --------------------------------------------------------------
    lo, hi = cfg["id_ranges"]["eon"]
    nums = rng.choice(np.arange(lo, hi + 1), size=Ne, replace=False)
    ents["EON_ID"] = [f"{cfg['id_prefixes']['eon']}{n}" for n in nums]
    ents["APPLICATION_NAME"] = [f"Application_{i + 1:05d}" for i in range(Ne)]
    ents["GRN"] = [f"grn:/synthetic/domain/application_{i + 1:05d}" for i in range(Ne)]

    # ---- observation plan -----------------------------------------------------------
    mp = norm_probs(O["metrics_per_entity_probs"])
    n_m = rng.choice(np.arange(1, len(mp) + 1), size=Ne, p=mp)
    raw = rng.lognormal(0.0, O["lognormal_sigma"], size=Ne)
    counts = _scale_counts(raw, T * n_m, cfg["row_count"], rng)
    gap_p = norm_probs(O["gap_probs"])
    anc_names = list(O["anchor_probs"].keys())
    anc = rng.choice(anc_names, size=Ne, p=norm_probs(list(O["anchor_probs"].values())))
    mw = L["metric_weights"]
    fam = L["metrics"]["family_idx"].to_numpy()
    plan_e, plan_m, plan_t = [], [], []
    n_metrics_eff = np.zeros(Ne, dtype=int)
    primary_metric = np.zeros(Ne, dtype=int)
    for e in range(Ne):
        nm = int(n_m[e])
        k = _split_counts(rng, int(counts[e]), nm, O["metric_split_weights"], T)
        nm_eff = int((k > 0).sum())
        # choose the metric set: primary by Zipf weight, secondary preferably from the same family
        chosen = [int(rng.choice(M, p=mw))]
        while len(chosen) < nm_eff:
            if rng.random() < O["same_family_prob"]:
                pool = [m for m in range(M) if fam[m] == fam[chosen[0]] and m not in chosen]
            else:
                pool = []
            if not pool:
                pool = [m for m in range(M) if m not in chosen]
            w = mw[pool]
            chosen.append(int(rng.choice(pool, p=w / w.sum())))
        g = int(rng.choice(len(gap_p), p=gap_p))
        Le = int(min(T, k.max() + g))
        a = {"end": T - Le, "start": 0}.get(anc[e], None)
        if a is None:
            a = int(rng.integers(0, T - Le + 1))
        window = np.arange(a, a + Le)
        for j in range(nm_eff):
            months = np.sort(rng.choice(window, size=int(k[j]), replace=False))
            plan_e.extend([e] * len(months))
            plan_m.extend([chosen[j]] * len(months))
            plan_t.extend(months.tolist())
        n_metrics_eff[e] = nm_eff
        primary_metric[e] = chosen[0]
    plan = pd.DataFrame({"eidx": plan_e, "midx": plan_m, "t": plan_t})
    assert len(plan) == cfg["row_count"], "observation plan row count mismatch"
    span = plan.groupby("eidx")["t"].agg(["min", "max", "nunique"])
    first = span["min"].to_numpy()
    last = span["max"].to_numpy()
    ents["n_obs"] = counts
    ents["n_metrics"] = n_metrics_eff
    ents["primary_metric_idx"] = primary_metric
    ents["first_t"], ents["last_t"], ents["n_months_observed"] = first, last, span["nunique"].to_numpy()

    # ---- scenarios -------------------------------------------------------------------
    sc_names = list(SC["fractions"].keys())
    sc_p = np.array([SC["fractions"][s] for s in sc_names])
    spanlen = last - first + 1
    scen = np.empty(Ne, dtype=object)
    u = rng.random(Ne)
    for e in range(Ne):
        ok = np.array([spanlen[e] >= SC["min_span_months"].get(s, 1) for s in sc_names], float)
        p = sc_p * ok
        p = p / p.sum()
        scen[e] = sc_names[int(np.searchsorted(np.cumsum(p), u[e], side="right").clip(0, len(sc_names) - 1))]
    ents["scenario"] = scen
    q0, q1 = SC["switch_quantile_range"]
    sw = first + np.rint((q0 + (q1 - q0) * rng.random(Ne)) * np.maximum(spanlen - 1, 0)).astype(int)
    sw = np.where(np.isin(scen, ["deteriorating", "improving_after_remediation"]),
                  np.clip(sw, first + 1, np.maximum(last - 1, first + 1)), first)
    ents["switch_t"] = sw
    p0 = np.zeros(Ne)
    p1 = np.zeros(Ne)
    for s in sc_names:
        m = scen == s
        spec = SC["p_fail"][s]
        if "uniform" in spec:
            v = rng.uniform(spec["uniform"][0], spec["uniform"][1], size=m.sum())
            p0[m], p1[m] = v, v
        else:
            p0[m], p1[m] = spec["start"], spec["end"]
    ents["p_fail_start"], ents["p_fail_end"] = p0, p1
    ents["rfb_scale"] = [SC["rfb_scale"].get(s, 1.0) for s in scen]

    # ---- application attributes: latent criticality-style factor (numeric co-movement only) --------
    z = rng.standard_normal(Ne)
    ld = EN["latent_loading"]

    def latent(rho):
        return rho * z + math.sqrt(1 - rho ** 2) * rng.standard_normal(Ne)

    tier_b = digitize_normal(latent(ld["tier"]), EN["application_tier"]) + 1
    rto_b = digitize_normal(latent(ld["rto"]), EN["application_rto_probs"])
    A_b = digitize_normal(latent(ld["arr"]), EN["arr_probs"]["A"]) + 1
    C_b = digitize_normal(latent(ld["arr"]), EN["arr_probs"]["C"]) + 1
    I_b = digitize_normal(latent(ld["arr"]), EN["arr_probs"]["I"]) + 1
    P_b = np.clip(np.rint((A_b + C_b + I_b) / 3.0 + rng.normal(0, EN["p_code_noise_sd"], size=Ne)), 1, 4).astype(int)
    kbs = rng.random(Ne) < sigmoid(logit(EN["critical_kbs_base_rate"]) + EN["critical_kbs_loading"] * z)
    ents["kbs"] = np.where(kbs, "Y", "N")
    life_labels = np.array(EN["lifecycle_labels"], dtype=object)
    life_b = rng.choice(len(life_labels), size=Ne, p=norm_probs(EN["lifecycle_probs"]))
    life_b_name = life_labels[life_b]
    ents["life_base"] = life_b_name
    nxt = {LIFECYCLE_ORDER[i]: LIFECYCLE_ORDER[min(i + 1, len(LIFECYCLE_ORDER) - 1)] for i in range(len(LIFECYCLE_ORDER))}
    ents["life_alt"] = [nxt[x] for x in life_b_name]
    CR = cfg["change_rates"]
    ents["life_t"] = _change_times(rng, CR["lifecycle"], ents["life_base"], ents["life_alt"], first, last)

    ents["tier_base"] = tier_b
    ents["tier_alt"] = np.clip(tier_b + np.where(rng.random(Ne) < 0.5, -1, 1), 1, 4)
    ents["tier_alt"] = np.where(ents["tier_alt"] == tier_b, np.where(tier_b == 1, 2, tier_b - 1), ents["tier_alt"])
    ents["tier_t"] = _change_times(rng, CR["tier"], ents["tier_base"], ents["tier_alt"], first, last)

    ents["rto_base"] = rto_b
    nrb = len(EN["application_rto_labels"])
    ents["rto_alt"] = np.clip(rto_b + np.where(rng.random(Ne) < 0.5, -1, 1), 0, nrb - 1)
    ents["rto_alt"] = np.where(ents["rto_alt"] == rto_b, np.where(rto_b == 0, 1, rto_b - 1), ents["rto_alt"])
    ents["rto_t"] = _change_times(rng, CR["rto"], ents["rto_base"], ents["rto_alt"], first, last)

    # risk: one component moves +/-1; overall code moves with probability 0.5
    sign = np.where(rng.random(Ne) < 0.5, -1, 1)
    comp = rng.integers(0, 3, size=Ne)
    A_a, C_a, I_a = A_b.copy(), C_b.copy(), I_b.copy()
    A_a = np.where(comp == 0, np.clip(A_b + sign, 1, 4), A_b)
    C_a = np.where(comp == 1, np.clip(C_b + sign, 1, 4), C_b)
    I_a = np.where(comp == 2, np.clip(I_b + sign, 1, 4), I_b)
    P_a = np.where(rng.random(Ne) < 0.5, np.clip(P_b + sign, 1, 4), P_b)
    for nm, b_, a_ in (("A", A_b, A_a), ("C", C_b, C_a), ("I", I_b, I_a), ("P", P_b, P_a)):
        ents[f"risk_{nm}_base"], ents[f"risk_{nm}_alt"] = b_, a_
    differs = (A_a != A_b) | (C_a != C_b) | (I_a != I_b) | (P_a != P_b)
    ents["risk_t"] = _change_times(rng, CR["risk"], np.zeros(Ne), differs.astype(int), first, last)

    # M&A (stable)
    ma = rng.random(Ne) < EN["ma_rate"]
    ents["ma"] = np.where(ma, "Y", "N")
    ents["acquired"] = np.where(ma, rng.choice(L["acquired_entities"], size=Ne, p=L["acquired_weights"]),
                                "NON_ACQUIRED_ENTITY")

    # ---- organisation, cost centre, owners, legal entity, buildings --------------------------------
    org2 = L["org2"]
    leaf_b = rng.choice(len(org2), size=Ne, p=L["org_leaf_weights"])
    leaf_a = rng.choice(len(org2), size=Ne, p=L["org_leaf_weights"])
    leaf_a = np.where(leaf_a == leaf_b, (leaf_b + 1 + rng.integers(0, len(org2) - 1, size=Ne)) % len(org2), leaf_a)
    sup_b = np.where(rng.random(Ne) < EN["super_department_level_rate"], "SUPER_DEPARTMENT", "DEPARTMENT")
    sup_a = np.where(rng.random(Ne) < EN["super_department_level_rate"], "SUPER_DEPARTMENT", "DEPARTMENT")
    ents["leaf_base"], ents["leaf_alt"] = leaf_b, leaf_a
    ents["gtype_base"], ents["gtype_alt"] = sup_b, sup_a
    ents["reorg_t"] = _change_times(rng, CR["reorg"], leaf_b, leaf_a, first, last)

    def pick_cc(leaf, u_):
        return L["cc_start"][leaf] + np.floor(u_ * L["cc_count"][leaf]).astype(int)

    u_cc = rng.random(Ne)
    cc_b = pick_cc(leaf_b, u_cc)
    cc_reorg = pick_cc(leaf_a, rng.random(Ne))
    cnt_b = L["cc_count"][leaf_b]
    pos_b = cc_b - L["cc_start"][leaf_b]
    cc_x = np.where(cnt_b > 1, L["cc_start"][leaf_b] + (pos_b + 1 + np.floor(rng.random(Ne) * np.maximum(cnt_b - 1, 1)).astype(int)) % np.maximum(cnt_b, 1), cc_b)
    ents["cc_base"], ents["cc_reorg"], ents["cc_alt"] = cc_b, cc_reorg, cc_x
    ents["cc_t"] = _change_times(rng, CR["cost_center"], cc_b, cc_x, first, last)
    ents.loc[ents["reorg_t"] < 99, "cc_t"] = 99          # reorg supersedes a within-department move

    sd_b = org2["sd_idx"].to_numpy()[leaf_b]
    sd_a = org2["sd_idx"].to_numpy()[leaf_a]
    ents["sd_base"], ents["sd_alt"] = sd_b, sd_a

    le_b = np.zeros(Ne, dtype=int)
    for sd in np.unique(sd_b):
        idx = np.flatnonzero(sd_b == sd)
        le_b[idx] = rng.choice(len(L["legal_entities"]), size=len(idx), p=L["le_weights"][sd])
    le_a = (le_b + 1 + rng.integers(0, len(L["legal_entities"]) - 1, size=Ne)) % len(L["legal_entities"])
    ents["le_base"], ents["le_alt"] = le_b, le_a
    ents["le_t"] = _change_times(rng, CR["legal_entity"], le_b, le_a, first, last)

    bus_b = _pick_from_pools(rng, sd_b, L["bus_pools"], L["bus_pool_w"])
    bus_a = _alt_from_pools(rng, sd_b, bus_b, [np.sort(p) for p in L["bus_pools"]])
    it_b = _pick_from_pools(rng, sd_b, L["it_pools"], L["it_pool_w"])
    it_a = _alt_from_pools(rng, sd_b, it_b, [np.sort(p) for p in L["it_pools"]])
    ents["bus_base"], ents["bus_alt"] = bus_b, bus_a
    ents["bus_t"] = _change_times(rng, CR["bus_owner"], bus_b, bus_a, first, last)
    ents["it_base"], ents["it_alt"] = it_b, it_a
    ents["it_t"] = _change_times(rng, CR["it_owner"], it_b, it_a, first, last)

    nb = C["n_buildings"]
    own_bld = L["bus_people"]["building_idx"].to_numpy()[bus_b]
    bld_b = np.where(rng.random(Ne) < EN["building_follow_owner_prob"], own_bld,
                     rng.choice(nb, size=Ne, p=L["building_weights"]))
    bld_a = (bld_b + 1 + rng.integers(0, nb - 1, size=Ne)) % nb
    ents["bld_base"], ents["bld_alt"] = bld_b, bld_a
    ents["bld_t"] = _change_times(rng, CR["building"], bld_b, bld_a, first, last)

    # ---- exemption level preference per entity (used on Exempt rows) ----------------------------
    ents["exempt_level_idx"] = rng.choice(len(L["exemption_levels"]), size=Ne, p=L["exemption_weights"])

    # ---- RTO change-date history (nullable; always <= METRIC_DATE) --------------------------------
    me = L["month_ends"]
    win_start = me[0] - pd.offsets.MonthBegin(1) if me[0].day != 1 else me[0]
    win_start = pd.Timestamp(me[0].year, me[0].month, 1)
    pre = rng.random(Ne) < EN["rto_history_pre_window_share"]
    days_back = rng.integers(1, 731, size=Ne)
    chg1 = pd.to_datetime(np.where(pre, (win_start - pd.to_timedelta(days_back, unit="D")).to_numpy(), np.datetime64("NaT", "ns")))
    ents["rto_chg1"] = chg1
    chg2 = pd.Series(pd.NaT, index=range(Ne), dtype="datetime64[ns]")
    extra = rng.random(Ne) < EN["rto_extra_in_window_date_share"]
    t_extra = first + np.floor(rng.random(Ne) * np.maximum(spanlen, 1)).astype(int)
    t_chg = np.where(ents["rto_t"] < 99, ents["rto_t"], np.where(extra, t_extra, -1))
    for e in np.flatnonzero(t_chg >= 0):
        tc = int(t_chg[e])
        end_ = me[tc]
        start_ = (me[tc - 1] + pd.Timedelta(days=1)) if tc > 0 else pd.Timestamp(end_.year, end_.month, 1)
        ndays = max(int((end_ - start_).days), 0)
        chg2.iloc[e] = start_ + pd.Timedelta(days=int(rng.integers(0, ndays + 1)))
    ents["rto_chg2"] = chg2.to_numpy()
    return ents, plan


# ======================================================================================
# 4. generate_rows
# ======================================================================================
def generate_rows(cfg: dict, L: dict, ents: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    rng = stage_rng(cfg, 3)
    RU, MS, SC = cfg["rules"], cfg["missingness"], cfg["scenarios"]
    EN = cfg["entity"]
    n = len(plan)
    e = plan["eidx"].to_numpy()
    mi = plan["midx"].to_numpy()
    t = plan["t"].to_numpy()

    def col(name):
        return ents[name].to_numpy()[e]

    def eff(prefix, tname=None):
        tt = col(tname or f"{prefix}_t")
        return np.where(t >= tt, col(f"{prefix}_alt"), col(f"{prefix}_base"))

    me = L["month_ends"]
    mdate = me.to_numpy()[t]
    out = {c: None for c in EXPECTED_COLUMNS}

    # ---- keys / dates -------------------------------------------------------------------------
    out["METRIC_ID"] = L["metrics"]["METRIC_ID"].to_numpy()[mi]
    out["METRIC_DATE"] = mdate
    out["METRIC_DATE_TYPE"] = L["metrics"]["date_type"].to_numpy()[mi]
    out["EON_ID"] = col("EON_ID")
    out["GRN"] = col("GRN")
    out["APPLICATION_NAME"] = col("APPLICATION_NAME")
    out["REPORTING_MONTHEND_DATE"] = mdate
    out["REPORTING_MONTH"] = me.month.to_numpy()[t]
    out["REPORTING_YEAR"] = me.year.to_numpy()[t]

    # ---- application attributes -----------------------------------------------------------------
    out["APPLICATION_TIER"] = eff("tier")
    out["APPLICATION_RTO"] = np.array(cfg["entity"]["application_rto_labels"], dtype=object)[eff("rto").astype(int)]
    out["LIFECYCLE_PHASE"] = eff("life")
    rt = col("risk_t")
    for nm in ("A", "C", "I", "P"):
        out[f"_risk_{nm}"] = np.where(t >= rt, col(f"risk_{nm}_alt"), col(f"risk_{nm}_base"))
    out["ASSET_RISK_RATING_2"] = np.array([f"P{v}" for v in out["_risk_P"]], dtype=object)
    out["ARR_AVAILABILITY"] = np.array([f"A{v}" for v in out["_risk_A"]], dtype=object)
    out["ARR_CONFIDENTIALITY"] = np.array([f"C{v}" for v in out["_risk_C"]], dtype=object)
    out["ARR_INTEGRITY"] = np.array([f"I{v}" for v in out["_risk_I"]], dtype=object)
    kb = col("kbs")
    out["HAS_CTIRICAL_KBS"] = kb
    flip = rng.random(n) < EN["kbs_flag_disagreement_rate"]
    out["KBS_FLAG_FLAG"] = np.where(flip, np.where(kb == "Y", "N", "Y"), kb)
    out["IS_MERGERS_ACQUISITIONS_ASSET"] = col("ma")
    out["ACQUIRED_ENTITY"] = col("acquired")

    # ---- organisation ------------------------------------------------------------------------------
    reorg_t = col("reorg_t")
    leaf = np.where(t >= reorg_t, col("leaf_alt"), col("leaf_base")).astype(int)
    gtype = np.where(t >= reorg_t, col("gtype_alt"), col("gtype_base"))
    o2, o1 = L["org2"], L["org1"]
    l1 = L["org2_to_org1"][leaf]
    is_dep = gtype == "DEPARTMENT"
    out["ORG_GROUP_TYPE"] = gtype
    out["SUPER_DIVISION"] = o2["top"].to_numpy()[leaf]
    out["DIVISION"] = o2["div"].to_numpy()[leaf]
    out["SUPER_DEPARTMENT"] = o2["sdp"].to_numpy()[leaf]
    out["DEPARTMENT"] = np.where(is_dep, o2["dep"].to_numpy()[leaf], None)
    out["BUS_ORG_LG_NM"] = np.where(is_dep, o2["bus_dep"].to_numpy()[leaf], o2["bus_sdp"].to_numpy()[leaf])
    out["BU_SUPER_DIVISION"] = o1["top"].to_numpy()[l1]
    out["BU_DIVISION"] = o1["div"].to_numpy()[l1]
    out["BU_SUPER_DEPARTMENT"] = o1["sdp"].to_numpy()[l1]
    out["BU_DEPARTMENT"] = np.where(is_dep, o1["dep"].to_numpy()[l1], None)
    cc = np.where(t >= reorg_t, col("cc_reorg"), np.where(t >= col("cc_t"), col("cc_alt"), col("cc_base"))).astype(int)
    out["COST_CENTER_CODE"] = L["cost_centers"]["code"].to_numpy()[cc]
    out["COST_CENTER_NAME"] = L["cost_centers"]["name"].to_numpy()[cc]

    # ---- legal entity & grouping flags ---------------------------------------------------------------
    le = eff("le").astype(int)
    LE = L["legal_entities"]
    out["LEGAL_ENTITY_CODE"] = LE["code"].to_numpy()[le]
    out["LEGAL_ENTITY_NAME"] = LE["name"].to_numpy()[le]
    for c in BANK_FLAG_COLS:
        out[c] = LE[c].to_numpy()[le]
    out["USBANKS_LE_LIST"] = np.array(LE["list"].tolist(), dtype=object)[le]

    # ---- owners, buildings --------------------------------------------------------------------------------
    bus = eff("bus").astype(int)
    it = eff("it").astype(int)
    BP, IP = L["bus_people"], L["it_people"]
    out["PRIMARY_BUS_FIRST_NAME"] = BP["first"].to_numpy()[bus]
    out["PRIMARY_BUS_LAST_NAME"] = BP["last"].to_numpy()[bus]
    out["PRIMARY_IT_FIRST_NAME"] = IP["first"].to_numpy()[it]
    out["PRIMARY_IT_LAST_NAME"] = IP["last"].to_numpy()[it]
    B = L["buildings"]
    bld = eff("bld").astype(int)
    out["BUILDING_NAME"] = B["building"].to_numpy()[bld]
    out["EVENT_LOCATION"] = B["location"].to_numpy()[bld]
    ebld = BP["building_idx"].to_numpy()[bus]
    out["EMPLOYEE_BUILDING_NAME"] = B["building"].to_numpy()[ebld]
    out["EMPLOYEE_COUNTRY_NAME"] = B["country"].to_numpy()[ebld]

    # ---- RTO change date (latest change on/before METRIC_DATE) ---------------------------------------------
    c1 = col("rto_chg1").astype("datetime64[ns]")
    c2 = col("rto_chg2").astype("datetime64[ns]")
    md = mdate.astype("datetime64[ns]")
    use2 = (~np.isnat(c2)) & (c2 <= md)
    use1 = (~np.isnat(c1)) & (c1 <= md)
    rto_date = np.where(use2, c2, np.where(use1, c1, np.datetime64("NaT", "ns")))
    out["RTO_CHANGE_DATE"] = rto_date.astype("datetime64[ns]")

    # ====================== JOINT COMPLIANCE / TEST / RFB GENERATION ========================================
    sc_names = list(SC["fractions"].keys())
    scen = col("scenario")
    # (1) TEST_STATUS
    tsp = np.vstack([norm_probs(SC["test_status_probs"][s]) for s in scen])
    ts_idx = np.minimum((rng.random(n)[:, None] > np.cumsum(tsp, axis=1)).sum(axis=1), 3)
    ts = np.array(TEST_STATUSES, dtype=object)[ts_idx]
    # (2) failure probability for completed tests (ramp around the entity's switch month)
    w = np.clip((t - col("switch_t")) / SC["ramp_months"] + 0.5, 0.0, 1.0)
    p_fail = col("p_fail_start") + (col("p_fail_end") - col("p_fail_start")) * w
    p_fail = sigmoid(logit(p_fail) + L["metrics"]["nc_logit_offset"].to_numpy()[mi])
    fail = rng.random(n) < p_fail
    tc = ts == "Test_Complete"
    res_missing = tc & (rng.random(n) < MS["TEST_RESULT_when_test_complete"])
    result = np.full(n, None, dtype=object)
    result[tc & fail] = "Fail"
    result[tc & ~fail] = "Pass"
    result[res_missing] = None
    res_key = np.where(result == "Pass", "Pass", np.where(result == "Fail", "Fail", "None"))
    # (3) COMPLIANCE_STATUS from the rule table
    ckey = np.empty(n, dtype=object)
    for i in range(n):
        s_ = ts[i]
        if s_ == "Test_Complete":
            ckey[i] = f"TC|{res_key[i]}"
        elif s_ == "No_Test":
            k_ = f"NT|{scen[i]}"
            ckey[i] = k_ if k_ in RU["compliance_given_test"] else "NT|default"
        elif s_ == "Test_Pending":
            ckey[i] = "TP|any"
        else:
            ckey[i] = "EX|any"
    status = sample_categorical(rng, ckey, RU["compliance_given_test"])
    # (4) COMPLIANCE_REASON consistent with status x test status x result
    rkey = np.array([f"{a}|{b}|{c}" for a, b, c in zip(status, ts, np.where(tc, res_key, "None"))], dtype=object)
    reason = sample_categorical(rng, rkey, RU["reason_table"])
    post = (scen == "improving_after_remediation") & (t >= col("switch_t")) & (rkey == "Compliant|Test_Complete|Pass")
    if post.any():
        tbl = {"x": RU["improving_post_switch_reasons"]}
        reason[post] = sample_categorical(rng, np.array(["x"] * int(post.sum()), dtype=object), tbl)
    # (5) EXEMPTION_LEVEL_1
    labels = L["exemption_levels"]
    ex = np.full(n, None, dtype=object)
    is_ex = ts == "Exempt"
    own = labels[col("exempt_level_idx")]
    rand_lvl = rng.choice(labels, size=n, p=L["exemption_weights"])
    ex_val = np.where(rng.random(n) < EN["exemption_entity_level_prob"], own, rand_lvl)
    ex[is_ex] = ex_val[is_ex]
    ex[is_ex & (rng.random(n) < MS["EXEMPTION_LEVEL_1_when_exempt"])] = None
    oth = (~is_ex) & (rng.random(n) < MS["EXEMPTION_LEVEL_1_populated_when_not_exempt"])
    ex[oth] = rand_lvl[oth]
    # (6) SYSTEM_RTC
    p_rtc = np.array([RU["system_rtc_prob_by_status"][s] for s in status])
    rtc = (rng.random(n) < p_rtc).astype(int)
    # (7) RFB / TOTAL_RFB
    pz = np.array([RU["rfb"][s]["p_zero"] for s in status])
    lam = np.array([RU["rfb"][s]["lam"] for s in status]) * col("rfb_scale")
    nz = rng.random(n) > pz
    rfb = np.where(nz, 1 + rng.poisson(lam), 0).astype(float)
    grp = pd.factorize(e.astype(np.int64) * 1000 + t)[0]
    ng = grp.max() + 1
    g_sum = np.bincount(grp, weights=rfb, minlength=ng)
    g_pf = np.bincount(grp, weights=p_fail, minlength=ng) / np.bincount(grp, minlength=ng)
    tr = RU["total_rfb_extra"]
    g_extra = rng.poisson(tr["base_lambda"] + tr["per_failure_prob"] * g_pf)
    total = (g_sum + g_extra)[grp]
    rfb_out = pd.array(rfb.astype(int), dtype="Int64")
    tot_out = pd.array(total.astype(int), dtype="Int64")
    rfb_out[rng.random(n) < MS["RFB"]] = pd.NA
    tot_out[rng.random(n) < MS["TOTAL_RFB"]] = pd.NA
    # (8) numerator / denominator (metric-specific denominator scope; PROVISIONAL)
    variant = L["metrics"]["denominator_variant"].to_numpy()[mi]
    in_a = np.isin(status, RU["denominator_variants"]["A"])
    in_b = np.isin(status, RU["denominator_variants"]["B"])
    den = np.where(variant == "A", in_a, in_b).astype(int)
    num = (np.isin(status, RU["numerator_statuses"]) & (den == 1)).astype(int)

    out["TEST_STATUS"], out["TEST_RESULT"] = ts, result
    out["COMPLIANCE_STATUS"], out["COMPLIANCE_REASON"] = status, reason
    out["EXEMPTION_LEVEL_1"] = ex
    out["SYSTEM_RTC"] = rtc
    out["RFB"], out["TOTAL_RFB"] = rfb_out, tot_out
    out["IS_NUMERATOR"], out["IS_DENOMINATOR"] = num, den

    df = pd.DataFrame({c: out[c] for c in EXPECTED_COLUMNS})
    # randomise final row order (documented, reproducible)
    perm = rng.permutation(n)
    df = df.iloc[perm].reset_index(drop=True)
    return df


# ======================================================================================
# 5. enforce_rules  (safety net -- every repair is counted; ideally all zero)
# ======================================================================================
def finalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    df = df[EXPECTED_COLUMNS].copy()
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c])
    for c in INT_COLS:
        df[c] = pd.array(pd.to_numeric(df[c], errors="coerce"), dtype="Int64")
    return df


def enforce_rules(df: pd.DataFrame, cfg: dict, L: dict):
    df = finalize_dtypes(df)
    rep = {}

    # dates / derivations
    bad = df["METRIC_DATE"] != df["REPORTING_MONTHEND_DATE"]
    rep["metric_date_realigned"] = int(bad.sum())
    df.loc[bad, "METRIC_DATE"] = df.loc[bad, "REPORTING_MONTHEND_DATE"]
    mth = df["REPORTING_MONTHEND_DATE"].dt.month.astype("Int64")
    yr = df["REPORTING_MONTHEND_DATE"].dt.year.astype("Int64")
    rep["month_year_rederived"] = int((df["REPORTING_MONTH"] != mth).sum() + (df["REPORTING_YEAR"] != yr).sum())
    df["REPORTING_MONTH"], df["REPORTING_YEAR"] = mth, yr

    # RTO change date must not be after METRIC_DATE
    late = df["RTO_CHANGE_DATE"].notna() & (df["RTO_CHANGE_DATE"] > df["METRIC_DATE"])
    rep["rto_change_date_nulled"] = int(late.sum())
    df.loc[late, "RTO_CHANGE_DATE"] = pd.NaT

    # test result only with a completed test
    nt = (df["TEST_STATUS"] != "Test_Complete") & df["TEST_RESULT"].notna()
    rep["test_result_nulled_without_test"] = int(nt.sum())
    df.loc[nt, "TEST_RESULT"] = None

    # TOTAL_RFB >= RFB
    low = df["RFB"].notna() & df["TOTAL_RFB"].notna() & (df["TOTAL_RFB"] < df["RFB"])
    rep["total_rfb_raised_to_rfb"] = int(low.sum())
    df.loc[low, "TOTAL_RFB"] = df.loc[low, "RFB"]

    # numerator <= denominator
    nb = df["IS_NUMERATOR"] > df["IS_DENOMINATOR"]
    rep["numerator_clipped"] = int(nb.sum())
    df.loc[nb, "IS_NUMERATOR"] = df.loc[nb, "IS_DENOMINATOR"]

    # organisation level consistency
    sup = df["ORG_GROUP_TYPE"] == "SUPER_DEPARTMENT"
    leak = sup & (df["DEPARTMENT"].notna() | df["BU_DEPARTMENT"].notna())
    rep["department_nulled_at_super_level"] = int(leak.sum())
    df.loc[sup, ["DEPARTMENT", "BU_DEPARTMENT"]] = None

    # bank grouping list derived from flags
    flags = (df[BANK_FLAG_COLS] == "Y").to_numpy()
    lst = pd.Series(["|".join(b for b, f in zip(BANK_LABELS, row) if f) or None for row in flags], index=df.index, dtype=object)
    rep["bank_list_rederived"] = int(((lst.fillna("<N>")) != df["USBANKS_LE_LIST"].fillna("<N>")).sum())
    df["USBANKS_LE_LIST"] = lst

    # acquired entity vs flag
    ma_bad = ((df["IS_MERGERS_ACQUISITIONS_ASSET"] == "N") & (df["ACQUIRED_ENTITY"] != "NON_ACQUIRED_ENTITY")) | \
             ((df["IS_MERGERS_ACQUISITIONS_ASSET"] == "Y") & (df["ACQUIRED_ENTITY"] == "NON_ACQUIRED_ENTITY"))
    rep["acquired_entity_inconsistent"] = int(ma_bad.sum())  # reported only (cannot be repaired silently)

    # normalise missing-value representation in string columns (true nulls only)
    for c in [c for c in EXPECTED_COLUMNS if c not in DATE_COLS + INT_COLS]:
        s = df[c].astype(object)
        s = s.where(~s.isin(STRING_NULL_TOKENS), None)
        s = s.where(s.notna(), None)
        df[c] = s
    return finalize_dtypes(df), rep


# ======================================================================================
# 6. Source dictionary, canonical string frames, loaders
# ======================================================================================
def load_source_dictionary(cfg: dict):
    """Read the client's data dictionary (all worksheets, incl. hidden). Returns DataFrame or None."""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [cfg.get("source_dictionary_path"),
             os.path.join(here, "source_inputs", "Data_Dictionary_1.xlsx"),
             os.path.join(here, "Data_Dictionary_1.xlsx")]
    for p in cands:
        if p and os.path.exists(p):
            import openpyxl
            wb = openpyxl.load_workbook(p, data_only=True)
            for ws in wb.worksheets:                      # hidden sheets are included in the scan
                rows = list(ws.iter_rows(values_only=True))
                if rows and rows[0] and rows[0][0] == "Column Name":
                    df = pd.DataFrame(rows[1:], columns=list(rows[0]))
                    df = df.dropna(subset=["Column Name"]).reset_index(drop=True)
                    df.attrs["source_path"] = os.path.basename(p)
                    df.attrs["sheet_state"] = ws.sheet_state
                    return df
    return None


GEN_RULES = {
    "METRIC_ID": "Catalogue of configurable metrics (prefix+6 digits from a disjoint range); primary metric per application by Zipf weight, secondary metrics preferably from the same family.",
    "METRIC_DATE": "Equals REPORTING_MONTHEND_DATE (enforced).",
    "METRIC_DATE_TYPE": "Metric-level label from reporting.date_type_labels (default single value 'Monthend').",
    "IS_NUMERATOR": "PROVISIONAL: 1 when COMPLIANCE_STATUS is Compliant and the row is in the metric's denominator scope.",
    "IS_DENOMINATOR": "PROVISIONAL: metric variant A = Compliant+Non_Compliant; variant B = adds Pending; Not_Applicable always excluded.",
    "EON_ID": "Synthetic application key (prefix+6 digits from a disjoint range); one per generated application.",
    "BUILDING_NAME": "Application primary building; Zipf-weighted, follows business-owner building 60% of the time; controlled change.",
    "EVENT_LOCATION": "Deterministic function of BUILDING_NAME via the building->location lookup.",
    "APPLICATION_TIER": "1-4 from a latent factor (numeric co-movement only, no severity direction); controlled change +/-1.",
    "EXEMPTION_LEVEL_1": "Populated for ~97% of Exempt rows (entity-preferred level 85%); ~2% populated otherwise; Exemption_NN, Zipf.",
    "TEST_STATUS": "Scenario-driven categorical draw (Test_Complete / No_Test / Test_Pending / Exempt).",
    "TEST_RESULT": "Pass/Fail only when Test_Complete (0.8% missing); null otherwise. Fail probability follows scenario trajectory.",
    "SYSTEM_RTC": "PROVISIONAL Bernoulli by COMPLIANCE_STATUS (higher for Non_Compliant).",
    "RFB": "PROVISIONAL row-level count: zero-inflated Poisson by COMPLIANCE_STATUS; 1% missing.",
    "TOTAL_RFB": "PROVISIONAL: sum of RFB over the application-month plus Poisson 'other findings'; >= RFB; 1% missing.",
    "COMPLIANCE_STATUS": "Drawn from rule table conditioned on TEST_STATUS / TEST_RESULT / scenario.",
    "COMPLIANCE_REASON": "Drawn from reason table keyed by COMPLIANCE_STATUS|TEST_STATUS|TEST_RESULT.",
    "RTO_CHANGE_DATE": "Latest entity RTO change on/before METRIC_DATE; null if none; coincides with APPLICATION_RTO band changes.",
    "GRN": "grn:/synthetic/domain/application_NNNNN; stable per EON_ID.",
    "APPLICATION_NAME": "Application_NNNNN; one-to-one with EON_ID.",
    "APPLICATION_RTO": "Ordinal band label from latent factor (numeric co-movement only); controlled change +/-1 band.",
    "HAS_CTIRICAL_KBS": "Bernoulli (22% base, latent loading); stable per application.",
    "LIFECYCLE_PHASE": "Dominant Production; controlled change advances one phase (Planning>Development>Implementation>Production>Retirement).",
    "ASSET_RISK_RATING_2": "P1-P4 ~ rounded mean of A/C/I + noise; PROVISIONAL generator device, no severity direction.",
    "ARR_AVAILABILITY": "A1-A4 from latent factor; controlled change.",
    "ARR_CONFIDENTIALITY": "C1-C4 from latent factor; controlled change.",
    "ARR_INTEGRITY": "I1-I4 from latent factor; controlled change.",
    "IS_MERGERS_ACQUISITIONS_ASSET": "Bernoulli 8%; stable per application.",
    "ACQUIRED_ENTITY": "Acquired_Entity_NN (Zipf) when flag Y, else NON_ACQUIRED_ENTITY (never null).",
    "BU_SUPER_DIVISION": "Hierarchy 1 level 1 (deterministic from the department's mapped BU leaf).",
    "BU_DIVISION": "Hierarchy 1 level 2; child of BU_SUPER_DIVISION.",
    "BU_SUPER_DEPARTMENT": "Hierarchy 1 level 3; child of BU_DIVISION.",
    "BU_DEPARTMENT": "Hierarchy 1 level 4; null when ORG_GROUP_TYPE = SUPER_DEPARTMENT.",
    "ORG_GROUP_TYPE": "DEPARTMENT (88%) or SUPER_DEPARTMENT (12%); drives nulls in both department columns.",
    "SUPER_DIVISION": "Hierarchy 2 level 1.",
    "DIVISION": "Hierarchy 2 level 2; child of SUPER_DIVISION.",
    "SUPER_DEPARTMENT": "Hierarchy 2 level 3; child of DIVISION.",
    "DEPARTMENT": "Hierarchy 2 level 4; null when ORG_GROUP_TYPE = SUPER_DEPARTMENT.",
    "BUS_ORG_LG_NM": "Business_Org_ + numeric suffix of DEPARTMENT (or SUPER_DEPARTMENT at super level).",
    "COST_CENTER_CODE": "Prefix+5 digits; each cost centre belongs to one department; maps 1:1 to name.",
    "COST_CENTER_NAME": "Cost_Center_NNN; deterministic from code.",
    "EMPLOYEE_BUILDING_NAME": "Building of the business owner (person-level attribute).",
    "EMPLOYEE_COUNTRY_NAME": "Deterministic function of EMPLOYEE_BUILDING_NAME (Country_NN).",
    "PRIMARY_BUS_FIRST_NAME": "Fictional syllable-built first name; stable pair with last name per application.",
    "PRIMARY_BUS_LAST_NAME": "Fictional syllable-built last name; stable pair with first name.",
    "PRIMARY_IT_FIRST_NAME": "As business owner, from the IT owner pool.",
    "PRIMARY_IT_LAST_NAME": "As business owner, from the IT owner pool.",
    "LEGAL_ENTITY_CODE": "Prefix+4 digits; maps 1:1 to LEGAL_ENTITY_NAME; division-specific Zipf mix.",
    "LEGAL_ENTITY_NAME": "Legal_Entity_NN; deterministic from code.",
    "IS_USBANKS": "Legal-entity attribute: membership of generic grouping BANK_A.",
    "IS_MSBNA": "Legal-entity attribute: membership of generic grouping BANK_B.",
    "IS_MSPBNA": "Legal-entity attribute: membership of generic grouping BANK_C.",
    "USBANKS_LE_LIST": "Pipe-joined BANK_A|BANK_B|BANK_C derived from the three flags; null when none are Y.",
    "KBS_FLAG_FLAG": "Equals HAS_CTIRICAL_KBS (disagreement rate configurable, default 0).",
    "REPORTING_MONTHEND_DATE": "One of n_months consecutive month-end dates ending reporting.end_date.",
    "REPORTING_MONTH": "Derived from REPORTING_MONTHEND_DATE.",
    "REPORTING_YEAR": "Derived from REPORTING_MONTHEND_DATE.",
}


def _col_to_str_list(s: pd.Series, c: str) -> list:
    if c in DATE_COLS:
        return [None if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d") for v in s]
    if c in INT_COLS:
        return [None if pd.isna(v) else str(int(v)) for v in s]
    return [None if (v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v))) else str(v) for v in s]


def to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Typed frame -> canonical string frame (ISO dates, plain ints, true nulls = None)."""
    return pd.DataFrame({c: _col_to_str_list(df[c], c) for c in EXPECTED_COLUMNS}, dtype=object)


def _norm_cell(v):
    if v is None or v is pd.NaT or v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
        return pd.Timestamp(v).strftime("%Y-%m-%d")
    if isinstance(v, (bool, np.bool_)):
        return str(v)
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else repr(float(v))
    s = str(v)
    return None if s == "" else s


def load_csv_canonical(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")
    return pd.DataFrame({c: [None if pd.isna(v) else v for v in raw[c]] for c in raw.columns}, dtype=object)


def load_xlsx_canonical(path: str, sheet: str = "Data") -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, dtype=object, keep_default_na=False, na_values=[""], engine="openpyxl")
    return pd.DataFrame({c: [_norm_cell(v) for v in raw[c]] for c in raw.columns}, dtype=object)


def coerce_types(raw: pd.DataFrame):
    """Canonical string frame -> typed frame; also returns count of cells that failed to parse."""
    out, issues = {}, {}
    for c in raw.columns:
        s = raw[c]
        if c in DATE_COLS:
            p = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
            issues[c] = int((s.notna() & p.isna()).sum())
            out[c] = p
        elif c in INT_COLS:
            p = pd.to_numeric(s, errors="coerce")
            issues[c] = int((s.notna() & p.isna()).sum())
            out[c] = pd.array(p, dtype="Int64") if issues[c] == 0 else p
        else:
            out[c] = s
    df = pd.DataFrame(out)
    return df, {k: v for k, v in issues.items() if v}


# ======================================================================================
# 7. disclosure_scan
# ======================================================================================
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CAMEL = re.compile(r"([a-z])([A-Z])")


def column_whitelist(cfg: dict, L: dict) -> dict:
    """Allowed value shape per string column. Anything outside => 'proprietary-looking' finding."""
    P = cfg["id_prefixes"]
    q = re.escape
    R = cfg["rules"]
    reasons = sorted({r for tbl in R["reason_table"].values() for r in tbl})
    name_re = r"[A-Z][a-z]{2,15}"
    ent = cfg["entity"]
    return {
        "METRIC_ID": re.compile(rf"{q(P['metric'])}\d{{6}}"),
        "METRIC_DATE_TYPE": set(cfg["reporting"]["date_type_labels"]),
        "EON_ID": re.compile(rf"{q(P['eon'])}\d{{6}}"),
        "BUILDING_NAME": re.compile(r"Building_\d{3}"),
        "EVENT_LOCATION": re.compile(r"Location_\d{3}"),
        "EXEMPTION_LEVEL_1": re.compile(r"Exemption_\d{2}"),
        "TEST_STATUS": set(TEST_STATUSES),
        "TEST_RESULT": {"Pass", "Fail"},
        "COMPLIANCE_STATUS": set(COMPLIANCE_STATUSES),
        "COMPLIANCE_REASON": set(reasons),
        "GRN": re.compile(r"grn:/synthetic/domain/application_\d{5}"),
        "APPLICATION_NAME": re.compile(r"Application_\d{5}"),
        "APPLICATION_RTO": set(ent["application_rto_labels"]),
        "HAS_CTIRICAL_KBS": {"Y", "N"},
        "LIFECYCLE_PHASE": set(ent["lifecycle_labels"]),
        "ASSET_RISK_RATING_2": re.compile(r"P[1-4]"),
        "ARR_AVAILABILITY": re.compile(r"A[1-4]"),
        "ARR_CONFIDENTIALITY": re.compile(r"C[1-4]"),
        "ARR_INTEGRITY": re.compile(r"I[1-4]"),
        "IS_MERGERS_ACQUISITIONS_ASSET": {"Y", "N"},
        "ACQUIRED_ENTITY": re.compile(r"NON_ACQUIRED_ENTITY|Acquired_Entity_\d{2}"),
        "BU_SUPER_DIVISION": re.compile(r"BU_Super_Division_\d{2}"),
        "BU_DIVISION": re.compile(r"BU_Division_\d{2}_\d{2}"),
        "BU_SUPER_DEPARTMENT": re.compile(r"BU_Super_Department_\d{2}_\d{2}_\d{2}"),
        "BU_DEPARTMENT": re.compile(r"BU_Department_\d{2}_\d{2}_\d{2}_\d{2}"),
        "ORG_GROUP_TYPE": {"DEPARTMENT", "SUPER_DEPARTMENT"},
        "SUPER_DIVISION": re.compile(r"Super_Division_\d{2}"),
        "DIVISION": re.compile(r"Division_\d{2}_\d{2}"),
        "SUPER_DEPARTMENT": re.compile(r"Super_Department_\d{2}_\d{2}_\d{2}"),
        "DEPARTMENT": re.compile(r"Department_\d{2}_\d{2}_\d{2}_\d{2}"),
        "BUS_ORG_LG_NM": re.compile(r"Business_Org_\d{2}_\d{2}_\d{2}(_\d{2})?"),
        "COST_CENTER_CODE": re.compile(rf"{q(P['cost_center'])}\d{{5}}"),
        "COST_CENTER_NAME": re.compile(r"Cost_Center_\d{3}"),
        "EMPLOYEE_BUILDING_NAME": re.compile(r"Building_\d{3}"),
        "EMPLOYEE_COUNTRY_NAME": re.compile(r"Country_\d{2}"),
        "PRIMARY_BUS_FIRST_NAME": re.compile(name_re),
        "PRIMARY_BUS_LAST_NAME": re.compile(name_re),
        "PRIMARY_IT_FIRST_NAME": re.compile(name_re),
        "PRIMARY_IT_LAST_NAME": re.compile(name_re),
        "LEGAL_ENTITY_CODE": re.compile(rf"{q(P['legal_entity'])}\d{{4}}"),
        "LEGAL_ENTITY_NAME": re.compile(r"Legal_Entity_\d{2}"),
        "IS_USBANKS": {"Y", "N"}, "IS_MSBNA": {"Y", "N"}, "IS_MSPBNA": {"Y", "N"},
        "USBANKS_LE_LIST": re.compile(r"BANK_[ABC](\|BANK_[ABC]){0,2}"),
        "KBS_FLAG_FLAG": {"Y", "N"},
    }


def disclosure_scan(df: pd.DataFrame, cfg: dict, L: dict) -> dict:
    """Deny-list + shape-whitelist scan of every string VALUE. FAIL on any finding.
    Extend the deny-list via PROFILE_CONFIG['validation']['extra_forbidden_terms']."""
    forb = set(FORBIDDEN_TERMS) | {t.lower() for t in cfg["validation"]["extra_forbidden_terms"]}
    wl = column_whitelist(cfg, L)
    name_cols = {"PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME", "PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME"}
    id_ranges = {"EON_ID": ("eon", cfg["id_prefixes"]["eon"]), "METRIC_ID": ("metric", cfg["id_prefixes"]["metric"]),
                 "COST_CENTER_CODE": ("cost_center", cfg["id_prefixes"]["cost_center"]),
                 "LEGAL_ENTITY_CODE": ("legal_entity", cfg["id_prefixes"]["legal_entity"])}
    str_cols = [c for c in EXPECTED_COLUMNS if c not in DATE_COLS + INT_COLS and c in df.columns]
    by_check: dict = {}
    examples: list = []
    n_vals = 0

    def add(check, col, val):
        by_check[check] = by_check.get(check, 0) + 1
        if len(examples) < 12:
            examples.append({"check": check, "column": col, "value": str(val)[:40]})

    for c in str_cols:
        for v in df[c].dropna().astype(str).unique():
            n_vals += 1
            lv = v.lower()
            if EMAIL_RE.search(v):
                add("email_address", c, v)
            for sub in FORBIDDEN_SUBSTRINGS:
                if sub in lv:
                    add("forbidden_substring", c, v)
                    break
            toks = [t for t in re.split(r"[^a-z0-9]+", _CAMEL.sub(r"\1 \2", v).lower()) if t]
            if any(t in forb for t in toks):
                add("forbidden_term", c, v)
            if c in name_cols and (lv in REAL_FIRST_NAMES or lv in REAL_LAST_NAMES):
                add("real_person_name", c, v)
            if lv in STRING_NULL_TOKENS or v.strip() != v:
                add("null_like_string", c, v)
            rule = wl.get(c)
            if rule is not None:
                ok = (v in rule) if isinstance(rule, set) else bool(rule.fullmatch(v))
                if not ok:
                    add("shape_violation", c, v)
            if c in id_ranges:
                key, pre = id_ranges[c]
                lo, hi = cfg["id_ranges"][key]
                digits = v[len(pre):]
                if not (v.startswith(pre) and digits.isdigit() and lo <= int(digits) <= hi):
                    add("id_outside_synthetic_range", c, v)
    return {"status": "PASS" if not by_check else "FAIL", "n_findings": int(sum(by_check.values())),
            "columns_scanned": len(str_cols), "distinct_values_scanned": n_vals,
            "by_check": by_check, "examples": examples}


def disclosure_scan_selftest(cfg: dict, L: dict) -> bool:
    """The scanner must flag planted violations (proves it is wired correctly)."""
    bad = pd.DataFrame({
        "APPLICATION_NAME": ["Application_00001", "Goldman_Box", "alpha@beta.com"],
        "PRIMARY_BUS_FIRST_NAME": ["Zenita", "Robert", "Qu"],
        "EON_ID": ["EON000001", "EON610001", "EON610002"],
    })
    res = disclosure_scan(bad, cfg, L)
    return res["status"] == "FAIL" and res["n_findings"] >= 5


# ======================================================================================
# 8. Profiling statistics (shared by validation, report, JSON and workbook)
# ======================================================================================
STABILITY_GROUPS = {
    "application_name_grn": ["APPLICATION_NAME", "GRN"],
    "application_tier": ["APPLICATION_TIER"],
    "application_rto": ["APPLICATION_RTO"],
    "lifecycle_phase": ["LIFECYCLE_PHASE"],
    "risk_ratings": ["ASSET_RISK_RATING_2", "ARR_AVAILABILITY", "ARR_CONFIDENTIALITY", "ARR_INTEGRITY"],
    "critical_kbs_flags": ["HAS_CTIRICAL_KBS", "KBS_FLAG_FLAG"],
    "ma_fields": ["IS_MERGERS_ACQUISITIONS_ASSET", "ACQUIRED_ENTITY"],
    "business_owner": ["PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"],
    "it_owner": ["PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME"],
    "organisation_both_hierarchies": ["BU_SUPER_DIVISION", "BU_DIVISION", "BU_SUPER_DEPARTMENT", "BU_DEPARTMENT",
                                      "ORG_GROUP_TYPE", "SUPER_DIVISION", "DIVISION", "SUPER_DEPARTMENT", "DEPARTMENT",
                                      "BUS_ORG_LG_NM"],
    "cost_centre": ["COST_CENTER_CODE", "COST_CENTER_NAME"],
    "legal_entity_and_flags": ["LEGAL_ENTITY_CODE", "LEGAL_ENTITY_NAME", "IS_USBANKS", "IS_MSBNA", "IS_MSPBNA", "USBANKS_LE_LIST"],
    "primary_building_location": ["BUILDING_NAME", "EVENT_LOCATION"],
    "employee_building_country": ["EMPLOYEE_BUILDING_NAME", "EMPLOYEE_COUNTRY_NAME"],
}
NEVER_CHANGE_GROUPS = {"application_name_grn", "critical_kbs_flags", "ma_fields"}


def _dist(s: pd.Series) -> dict:
    return {"min": float(s.min()), "p25": float(s.quantile(.25)), "median": float(s.median()),
            "mean": round(float(s.mean()), 3), "p75": float(s.quantile(.75)), "p90": float(s.quantile(.90)),
            "max": float(s.max())}


def compute_profile(df: pd.DataFrame, cfg: dict, L: dict, ents: pd.DataFrame) -> dict:
    n = len(df)
    P: dict = {"shape": {"rows": n, "columns": int(df.shape[1])}}
    cols = {}
    for c in EXPECTED_COLUMNS:
        s = df[c]
        vc = s.value_counts(dropna=True)
        nun = int(len(vc))
        info = {"dtype": str(s.dtype), "null_count": int(s.isna().sum()), "null_rate": round(float(s.isna().mean()), 6),
                "distinct": nun, "top1_share": round(float(vc.iloc[0] / n), 6) if nun else 0.0,
                "tail_share_lt_1pct": round(float(((vc / n) < 0.01).sum() / nun), 4) if nun else 0.0}
        if nun <= 60 and c not in DATE_COLS:
            info["top_values"] = [[str(k), round(float(v / n), 6)] for k, v in vc.head(5).items()]
        cols[c] = info
    P["columns"] = cols

    # dates / calendar
    P["dates"] = {c: {"min": df[c].min().strftime("%Y-%m-%d") if df[c].notna().any() else None,
                      "max": df[c].max().strftime("%Y-%m-%d") if df[c].notna().any() else None,
                      "distinct": int(df[c].nunique())} for c in DATE_COLS}
    me = list(L["month_ends"])
    tmap = {d: i for i, d in enumerate(me)}
    t = df["REPORTING_MONTHEND_DATE"].map(tmap)
    dfx = df.assign(_t=t)

    # entity repetition
    g = df.groupby("EON_ID")
    rows_per = g.size()
    months_per = g["REPORTING_MONTHEND_DATE"].nunique()
    metrics_per = g["METRIC_ID"].nunique()
    order = rows_per.sort_values(ascending=False)
    top_dec = int(math.ceil(0.1 * len(order)))
    P["entity_repetition"] = {
        "distinct_eon_id": int(len(rows_per)), "distinct_metric_id": int(df["METRIC_ID"].nunique()),
        "rows_per_eon": _dist(rows_per), "months_per_eon": _dist(months_per), "metrics_per_eon": _dist(metrics_per),
        "months_per_eon_histogram": {str(k): int(v) for k, v in months_per.value_counts().sort_index().items()},
        "metrics_per_eon_histogram": {str(k): int(v) for k, v in metrics_per.value_counts().sort_index().items()},
        "share_eon_with_2plus_months": round(float((months_per >= 2).mean()), 4),
        "share_eon_with_6plus_months": round(float((months_per >= 6).mean()), 4),
        "share_eon_with_all_months": round(float((months_per == len(me)).mean()), 4),
        "share_eon_single_observation": round(float((rows_per == 1).mean()), 4),
        "top_decile_eon_row_share": round(float(order.head(top_dec).sum() / n), 4),
        "largest_eon_row_share": round(float(order.iloc[0] / n), 4),
        "sparsity_note": "entities typically observed in a contiguous-ish window with gaps; not a full Cartesian grid",
    }
    mrows = df.groupby("METRIC_ID").size()
    P["metric_repetition"] = {"rows_per_metric": _dist(mrows),
                              "apps_per_metric": _dist(df.groupby("METRIC_ID")["EON_ID"].nunique()),
                              "months_per_metric": _dist(df.groupby("METRIC_ID")["REPORTING_MONTHEND_DATE"].nunique())}

    # per reporting period
    per = []
    for d in me:
        s = df[df["REPORTING_MONTHEND_DATE"] == d]
        sc = s["COMPLIANCE_STATUS"].value_counts()
        den, num = int(s["IS_DENOMINATOR"].sum()), int(s["IS_NUMERATOR"].sum())
        per.append({"date": d.strftime("%Y-%m-%d"), "rows": int(len(s)), "distinct_eon_id": int(s["EON_ID"].nunique()),
                    "distinct_metric_id": int(s["METRIC_ID"].nunique()),
                    **{f"status_{k}": int(sc.get(k, 0)) for k in COMPLIANCE_STATUSES},
                    **{f"test_{k}": int((s["TEST_STATUS"] == k).sum()) for k in TEST_STATUSES},
                    "failed_completed_tests": int(((s["TEST_STATUS"] == "Test_Complete") & (s["TEST_RESULT"] == "Fail")).sum()),
                    "provisional_compliance_rate": round(num / den, 4) if den else None})
    P["periods"] = per

    # stability within EON_ID
    stab = {}
    multi = rows_per[rows_per >= 2].index
    for name, cs in STABILITY_GROUPS.items():
        key = df[cs].fillna("<null>").astype(str).agg("|".join, axis=1)
        tmp = pd.DataFrame({"e": df["EON_ID"].values, "k": key.values})
        nun = tmp.groupby("e")["k"].nunique()
        modal = tmp.groupby(["e", "k"]).size().groupby("e").max()
        stab[name] = {"entities_with_2plus_rows": int(len(multi)),
                      "share_entities_with_change": round(float((nun.loc[multi] > 1).mean()), 4),
                      "share_rows_off_modal_value": round(float(1 - modal.sum() / n), 4)}
    P["stability"] = stab

    # organisation / reference cardinalities
    P["cardinalities"] = {
        "applications": int(df["EON_ID"].nunique()), "metrics": int(df["METRIC_ID"].nunique()),
        "buildings": int(df["BUILDING_NAME"].nunique()), "locations": int(df["EVENT_LOCATION"].nunique()),
        "employee_buildings": int(df["EMPLOYEE_BUILDING_NAME"].nunique()), "countries": int(df["EMPLOYEE_COUNTRY_NAME"].nunique()),
        "bu_super_divisions": int(df["BU_SUPER_DIVISION"].nunique()), "bu_divisions": int(df["BU_DIVISION"].nunique()),
        "bu_super_departments": int(df["BU_SUPER_DEPARTMENT"].nunique()), "bu_departments": int(df["BU_DEPARTMENT"].nunique()),
        "super_divisions": int(df["SUPER_DIVISION"].nunique()), "divisions": int(df["DIVISION"].nunique()),
        "super_departments": int(df["SUPER_DEPARTMENT"].nunique()), "departments": int(df["DEPARTMENT"].nunique()),
        "business_org_labels": int(df["BUS_ORG_LG_NM"].nunique()), "cost_centres": int(df["COST_CENTER_CODE"].nunique()),
        "legal_entities": int(df["LEGAL_ENTITY_CODE"].nunique()),
        "business_owners": int(df[["PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"]].drop_duplicates().shape[0]),
        "it_owners": int(df[["PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME"]].drop_duplicates().shape[0]),
    }

    # status x test cross-tab
    ct = pd.crosstab(df["TEST_STATUS"], df["COMPLIANCE_STATUS"])
    P["test_status_by_compliance_status"] = {r: {c: int(ct.loc[r, c]) if c in ct.columns else 0 for c in COMPLIANCE_STATUSES} for r in ct.index}
    ct2 = pd.crosstab(df["TEST_STATUS"], df["TEST_RESULT"].fillna("<null>"))
    P["test_status_by_test_result"] = {r: {str(c): int(ct2.loc[r, c]) for c in ct2.columns} for r in ct2.index}

    # entity-month non-compliance transitions (evidence of longitudinal change)
    em = dfx.assign(nc=(dfx["COMPLIANCE_STATUS"] == "Non_Compliant")).groupby(["EON_ID", "_t"])["nc"].max().reset_index()
    em = em.sort_values(["EON_ID", "_t"])
    em["prev_nc"] = em.groupby("EON_ID")["nc"].shift(1)
    em["gap"] = em.groupby("EON_ID")["_t"].diff()
    cons = em["gap"] == 1
    new_nc = em[cons & (em["prev_nc"] == False) & (em["nc"] == True)]  # noqa: E712
    resolved = em[cons & (em["prev_nc"] == True) & (em["nc"] == False)]  # noqa: E712
    persist = em[cons & (em["prev_nc"] == True) & (em["nc"] == True)]  # noqa: E712
    P["transitions"] = {
        "consecutive_month_pairs": int(cons.sum()), "new_non_compliance": int(len(new_nc)),
        "resolved_non_compliance": int(len(resolved)), "persistent_non_compliance": int(len(persist)),
        "new_non_compliance_by_month": {str(int(k)): int(v) for k, v in new_nc.groupby("_t").size().items()},
        "resolved_by_month": {str(int(k)): int(v) for k, v in resolved.groupby("_t").size().items()},
        "definition": "entity-month flag = any Non_Compliant row for the EON_ID in that month; consecutive observed months only",
    }

    # scenarios (entity-level shares + behaviour check)
    sc_tab = ents[["EON_ID", "scenario", "switch_t"]]
    m = dfx.merge(sc_tab, on="EON_ID", how="left")
    scen = {}
    for s_, grp in m.groupby("scenario"):
        tcn = (grp["TEST_STATUS"] == "Test_Complete")
        entry = {"entities": int(grp["EON_ID"].nunique()), "rows": int(len(grp)),
                 "non_compliant_share": round(float((grp["COMPLIANCE_STATUS"] == "Non_Compliant").mean()), 4),
                 "compliant_share": round(float((grp["COMPLIANCE_STATUS"] == "Compliant").mean()), 4),
                 "test_complete_share": round(float(tcn.mean()), 4),
                 "test_pending_share": round(float((grp["TEST_STATUS"] == "Test_Pending").mean()), 4),
                 "exempt_share": round(float((grp["TEST_STATUS"] == "Exempt").mean()), 4),
                 "no_test_share": round(float((grp["TEST_STATUS"] == "No_Test").mean()), 4),
                 "fail_share_of_completed": round(float((grp.loc[tcn, "TEST_RESULT"] == "Fail").mean()), 4) if tcn.any() else None}
        if s_ in ("deteriorating", "improving_after_remediation"):
            post = grp["_t"] >= grp["switch_t"]
            nc = grp["COMPLIANCE_STATUS"] == "Non_Compliant"
            entry["nc_share_before_switch"] = round(float(nc[~post].mean()), 4)
            entry["nc_share_after_switch"] = round(float(nc[post].mean()), 4)
        scen[str(s_)] = entry
    P["scenarios"] = scen
    P["scenario_entity_shares"] = {k: round(float(v), 4) for k, v in ents["scenario"].value_counts(normalize=True).items()}

    # risk vs compliance (guard against artificial perfect correlation)
    rk = {}
    for code, grp in df.groupby("ASSET_RISK_RATING_2"):
        tcn = grp["TEST_STATUS"] == "Test_Complete"
        rk[str(code)] = {"rows": int(len(grp)),
                         "non_compliant_share": round(float((grp["COMPLIANCE_STATUS"] == "Non_Compliant").mean()), 4),
                         "fail_share_of_completed": round(float((grp.loc[tcn, "TEST_RESULT"] == "Fail").mean()), 4) if tcn.any() else None}
    P["risk_vs_compliance"] = rk

    # duplicates / grain
    P["duplicates"] = {
        "EON_ID+METRIC_ID+METRIC_DATE (candidate row key)": int(df.duplicated(["EON_ID", "METRIC_ID", "METRIC_DATE"]).sum()),
        "full_row": int(df.duplicated().sum()),
        "EON_ID+METRIC_DATE (several metrics per app-month; informational)": int(df.duplicated(["EON_ID", "METRIC_DATE"]).sum()),
        "EON_ID+METRIC_ID (repeats across months; informational)": int(df.duplicated(["EON_ID", "METRIC_ID"]).sum()),
        "METRIC_ID+METRIC_DATE (repeats across apps; informational)": int(df.duplicated(["METRIC_ID", "METRIC_DATE"]).sum()),
    }
    return P


# ======================================================================================
# 9. validate_data
# ======================================================================================
class Results:
    def __init__(self):
        self.rows: list = []

    def add(self, check, ok, detail="", level="FAIL", section=""):
        self.rows.append({"section": section, "check": check, "status": "PASS" if ok else level, "detail": str(detail)})

    def counts(self):
        out = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for r in self.rows:
            out[r["status"]] += 1
        return out


def validate_data(df: pd.DataFrame, cfg: dict, L: dict, ents: pd.DataFrame, source: str = "memory",
                  raw: pd.DataFrame | None = None, parse_issues: dict | None = None,
                  dictionary: pd.DataFrame | None = None):
    """Full rule validation of a typed frame (run against RELOADED files, not just memory)."""
    R = Results()
    V, RU = cfg["validation"], cfg["rules"]
    n = len(df)

    # ---------------- schema (fail fast: nothing else is meaningful if the layout is wrong) ----------------
    S = "Schema"
    if list(df.columns) != EXPECTED_COLUMNS:
        missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
        R.add("Column names and order match specification", False,
              f"{df.shape[1]} columns; missing={missing[:5]} extra={extra[:5]} (order or names differ)", section=S)
        R.add("Exactly 57 columns", df.shape[1] == CONTRACT_COLS, str(df.shape[1]), section=S)
        return R.rows, None
    P = compute_profile(df, cfg, L, ents)
    R.add("Row count equals configured row_count", n == cfg["row_count"], f"{n:,} vs {cfg['row_count']:,}", section=S)
    R.add("Row count equals client contract (11,399)", n == CONTRACT_ROWS, f"{n:,}", "WARN", S)
    R.add("Exactly 57 columns", df.shape[1] == CONTRACT_COLS, str(df.shape[1]), section=S)
    R.add("Column names and order match specification", list(df.columns) == EXPECTED_COLUMNS, "", section=S)
    R.add("No duplicate column names", len(set(df.columns)) == len(df.columns), "", section=S)
    R.add("Spelling preserved: HAS_CTIRICAL_KBS and KBS_FLAG_FLAG", {"HAS_CTIRICAL_KBS", "KBS_FLAG_FLAG"} <= set(df.columns), "", section=S)
    R.add("Seed equals contract seed 20261103", cfg["seed"] == CONTRACT_SEED, str(cfg["seed"]), "WARN", S)
    if dictionary is not None:
        R.add("Dictionary column order identical to specification", dictionary["Column Name"].tolist() == EXPECTED_COLUMNS,
              f"{len(dictionary)} dictionary rows", section=S)
    if parse_issues is not None:
        R.add("Every date / integer cell parses", not parse_issues, parse_issues or "", section=S)
    if raw is not None:
        bad = sum(int((~raw[c].dropna().str.fullmatch(r"\d{4}-\d{2}-\d{2}")).sum()) for c in DATE_COLS)
        R.add("Dates stored as ISO YYYY-MM-DD", bad == 0, f"{bad} non-ISO cells", section=S)

    # ---------------- keys & nulls ----------------
    S = "Keys & nulls"
    must = [c for c in EXPECTED_COLUMNS if c not in NULLABLE_COLS]
    nn = df[must].isna().sum()
    R.add("All non-nullable columns fully populated (keys, reporting fields, hierarchy levels 1-3, ...)", int(nn.sum()) == 0,
          nn[nn > 0].to_dict() or f"{len(must)} columns checked", section=S)
    str_cols = [c for c in EXPECTED_COLUMNS if c not in DATE_COLS + INT_COLS]
    tok = {c: int(df[c].isin(STRING_NULL_TOKENS - {""}).sum()) for c in str_cols}
    tok = {k: v for k, v in tok.items() if v}
    R.add("Nulls are true missing values (no 'NULL'/'nan'/'None'/blank-string tokens)", not tok, tok or "", section=S)
    R.add("Identifier columns are text (not numeric)", all(not pd.api.types.is_numeric_dtype(df[c]) for c in
          ["METRIC_ID", "EON_ID", "GRN", "COST_CENTER_CODE", "LEGAL_ENTITY_CODE"]), "", section=S)

    # ---------------- domains ----------------
    S = "Domains"
    for c in ("IS_NUMERATOR", "IS_DENOMINATOR", "SYSTEM_RTC"):
        R.add(f"{c} in {{0,1}}", bool(df[c].isin([0, 1]).all()), "", section=S)
    R.add("APPLICATION_TIER in 1..4", bool(df["APPLICATION_TIER"].between(1, 4).all()), "", section=S)
    R.add("REPORTING_MONTH in 1..12 and REPORTING_YEAR 4-digit", bool(df["REPORTING_MONTH"].between(1, 12).all() and df["REPORTING_YEAR"].between(1000, 9999).all()), "", section=S)
    R.add("RFB and TOTAL_RFB non-negative integers where present", bool((df["RFB"].dropna() >= 0).all() and (df["TOTAL_RFB"].dropna() >= 0).all()), "", section=S)
    for c in YN_COLS:
        R.add(f"{c} contains only Y/N", bool(df[c].isin(["Y", "N"]).all()), "", section=S)
    for c, pat in (("ASSET_RISK_RATING_2", r"P[1-4]"), ("ARR_AVAILABILITY", r"A[1-4]"), ("ARR_CONFIDENTIALITY", r"C[1-4]"), ("ARR_INTEGRITY", r"I[1-4]")):
        R.add(f"{c} codes valid ({pat})", bool(df[c].str.fullmatch(pat).all()), "", section=S)
    R.add("TEST_STATUS vocabulary valid", bool(df["TEST_STATUS"].isin(TEST_STATUSES).all()), "", section=S)
    R.add("COMPLIANCE_STATUS vocabulary valid", bool(df["COMPLIANCE_STATUS"].isin(COMPLIANCE_STATUSES).all()), "", section=S)
    R.add("TEST_RESULT only Pass/Fail/null", bool(df["TEST_RESULT"].dropna().isin(["Pass", "Fail"]).all()), "", section=S)
    R.add("LIFECYCLE_PHASE vocabulary valid", bool(df["LIFECYCLE_PHASE"].isin(cfg["entity"]["lifecycle_labels"]).all()), "", section=S)
    R.add("APPLICATION_RTO vocabulary valid", bool(df["APPLICATION_RTO"].isin(cfg["entity"]["application_rto_labels"]).all()), "", section=S)
    R.add("METRIC_DATE_TYPE vocabulary valid", bool(df["METRIC_DATE_TYPE"].isin(cfg["reporting"]["date_type_labels"]).all()), "", section=S)

    # ---------------- dates ----------------
    S = "Dates"
    R.add("METRIC_DATE equals REPORTING_MONTHEND_DATE on every row", bool((df["METRIC_DATE"] == df["REPORTING_MONTHEND_DATE"]).all()), "", section=S)
    d = df["REPORTING_MONTHEND_DATE"]
    R.add("REPORTING_MONTHEND_DATE is a month-end", bool((d == d + pd.offsets.MonthEnd(0)).all()), "", section=S)
    R.add("Reporting dates are exactly the configured consecutive month-ends", set(d.unique()) == set(L["month_ends"]) and d.nunique() == cfg["reporting"]["n_months"],
          f"{d.nunique()} periods {d.min():%Y-%m-%d}..{d.max():%Y-%m-%d}", section=S)
    R.add("REPORTING_MONTH derived correctly", bool((df["REPORTING_MONTH"].astype(int) == d.dt.month).all()), "", section=S)
    R.add("REPORTING_YEAR derived correctly", bool((df["REPORTING_YEAR"].astype(int) == d.dt.year).all()), "", section=S)
    rc = df["RTO_CHANGE_DATE"]
    R.add("RTO_CHANGE_DATE null or <= METRIC_DATE", bool((rc.isna() | (rc <= df["METRIC_DATE"])).all()), f"{int((rc > df['METRIC_DATE']).sum())} violations", section=S)
    R.add("RTO_CHANGE_DATE missingness is moderate/high (often missing)", 0.2 <= rc.isna().mean() <= 0.95, f"{rc.isna().mean():.1%} null", "WARN", S)

    # ---------------- entity identity & stability ----------------
    S = "Entity identity & stability"
    R.add("EON_ID <-> APPLICATION_NAME one-to-one", df.groupby("EON_ID")["APPLICATION_NAME"].nunique().max() == 1 and df.groupby("APPLICATION_NAME")["EON_ID"].nunique().max() == 1, "", section=S)
    R.add("EON_ID <-> GRN one-to-one", df.groupby("EON_ID")["GRN"].nunique().max() == 1 and df.groupby("GRN")["EON_ID"].nunique().max() == 1, "", section=S)
    suffix_ok = (df["GRN"].str.extract(r"application_(\d{5})$")[0] == df["APPLICATION_NAME"].str.extract(r"Application_(\d{5})$")[0]).all()
    R.add("GRN suffix agrees with APPLICATION_NAME", bool(suffix_ok), "", section=S)
    R.add("Generated application set equals entity lookup", set(df["EON_ID"]) == set(ents["EON_ID"]), f"{df['EON_ID'].nunique()} vs {len(ents)}", section=S)
    for name, st in P["stability"].items():
        if name in NEVER_CHANGE_GROUPS:
            ok = st["share_entities_with_change"] == 0.0
        else:
            ok = st["share_entities_with_change"] <= V["max_entity_share_with_attribute_change"]
        R.add(f"Stable within EON_ID: {name}", ok,
              f"{st['share_entities_with_change']:.2%} of multi-row apps change; {st['share_rows_off_modal_value']:.2%} rows off modal", section=S)
    bp = df[["PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"]].drop_duplicates()
    lp = set(zip(L["bus_people"]["first"], L["bus_people"]["last"]))
    R.add("Business-owner (first,last) pairs all exist in the fictional-person lookup", set(map(tuple, bp.values)) <= lp, f"{len(bp)} pairs", section=S)
    ip = df[["PRIMARY_IT_FIRST_NAME", "PRIMARY_IT_LAST_NAME"]].drop_duplicates()
    lip = set(zip(L["it_people"]["first"], L["it_people"]["last"]))
    R.add("IT-owner (first,last) pairs all exist in the fictional-person lookup", set(map(tuple, ip.values)) <= lip, f"{len(ip)} pairs", section=S)
    ow = df.groupby(["PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"])["EMPLOYEE_BUILDING_NAME"].nunique().max()
    R.add("Business-owner pair maps to a single employee building", ow == 1, f"max {ow}", section=S)

    # ---------------- hierarchies & lookups ----------------
    S = "Hierarchies & lookups"
    for child, parent in (("DIVISION", "SUPER_DIVISION"), ("SUPER_DEPARTMENT", "DIVISION"), ("DEPARTMENT", "SUPER_DEPARTMENT"),
                          ("BU_DIVISION", "BU_SUPER_DIVISION"), ("BU_SUPER_DEPARTMENT", "BU_DIVISION"), ("BU_DEPARTMENT", "BU_SUPER_DEPARTMENT")):
        x = df[[child, parent]].dropna()
        R.add(f"{child} has exactly one {parent}", bool((x.groupby(child)[parent].nunique() <= 1).all()), "", section=S)
    o2, o1 = L["org2"], L["org1"]
    t3_2 = set(zip(o2["top"], o2["div"], o2["sdp"])); t4_2 = set(zip(o2["top"], o2["div"], o2["sdp"], o2["dep"]))
    t3_1 = set(zip(o1["top"], o1["div"], o1["sdp"])); t4_1 = set(zip(o1["top"], o1["div"], o1["sdp"], o1["dep"]))
    R.add("Hierarchy 2 paths exist in the lookup", set(zip(df.SUPER_DIVISION, df.DIVISION, df.SUPER_DEPARTMENT)) <= t3_2 and
          set(map(tuple, df.dropna(subset=["DEPARTMENT"])[["SUPER_DIVISION", "DIVISION", "SUPER_DEPARTMENT", "DEPARTMENT"]].values)) <= t4_2, "", section=S)
    R.add("Hierarchy 1 (BU_) paths exist in the lookup", set(zip(df.BU_SUPER_DIVISION, df.BU_DIVISION, df.BU_SUPER_DEPARTMENT)) <= t3_1 and
          set(map(tuple, df.dropna(subset=["BU_DEPARTMENT"])[["BU_SUPER_DIVISION", "BU_DIVISION", "BU_SUPER_DEPARTMENT", "BU_DEPARTMENT"]].values)) <= t4_1, "", section=S)
    dep_map = dict(zip(o2["dep"], o1["dep"].to_numpy()[L["org2_to_org1"]]))
    x = df.dropna(subset=["DEPARTMENT"])
    R.add("DEPARTMENT deterministically maps to one BU_DEPARTMENT", bool((x["DEPARTMENT"].map(dep_map) == x["BU_DEPARTMENT"]).all()), "", section=S)
    sup = df["ORG_GROUP_TYPE"] == "SUPER_DEPARTMENT"
    R.add("ORG_GROUP_TYPE consistent with populated level (DEPARTMENT => both dept cols; SUPER_DEPARTMENT => both null)",
          bool(df.loc[~sup, ["DEPARTMENT", "BU_DEPARTMENT"]].notna().all().all() and df.loc[sup, ["DEPARTMENT", "BU_DEPARTMENT"]].isna().all().all()),
          f"{sup.mean():.1%} rows at super-department level", section=S)
    exp_bus = np.where(df["DEPARTMENT"].notna(), df["DEPARTMENT"].fillna("").str.replace("Department_", "Business_Org_", n=1, regex=False),
                       df["SUPER_DEPARTMENT"].str.replace("Super_Department_", "Business_Org_", n=1, regex=False))
    R.add("BUS_ORG_LG_NM consistent with hierarchy", bool((df["BUS_ORG_LG_NM"].to_numpy() == exp_bus).all()), "", section=S)
    cc = L["cost_centers"]
    R.add("COST_CENTER_CODE <-> COST_CENTER_NAME one-to-one", df.groupby("COST_CENTER_CODE")["COST_CENTER_NAME"].nunique().max() == 1 and df.groupby("COST_CENTER_NAME")["COST_CENTER_CODE"].nunique().max() == 1, "", section=S)
    R.add("Cost-centre code/name pairs match the lookup", bool((df["COST_CENTER_CODE"].map(dict(zip(cc["code"], cc["name"]))) == df["COST_CENTER_NAME"]).all()), "", section=S)
    cc_dep = dict(zip(cc["code"], o2["dep"].to_numpy()[cc["leaf"].to_numpy()]))
    x = df.dropna(subset=["DEPARTMENT"])
    R.add("Cost centre belongs to the row's DEPARTMENT", bool((x["COST_CENTER_CODE"].map(cc_dep) == x["DEPARTMENT"]).all()), "", section=S)
    le = L["legal_entities"]
    R.add("LEGAL_ENTITY_CODE <-> LEGAL_ENTITY_NAME one-to-one", df.groupby("LEGAL_ENTITY_CODE")["LEGAL_ENTITY_NAME"].nunique().max() == 1 and df.groupby("LEGAL_ENTITY_NAME")["LEGAL_ENTITY_CODE"].nunique().max() == 1, "", section=S)
    R.add("Legal-entity code/name pairs match the lookup", bool((df["LEGAL_ENTITY_CODE"].map(dict(zip(le["code"], le["name"]))) == df["LEGAL_ENTITY_NAME"]).all()), "", section=S)
    flags_ok = all((df["LEGAL_ENTITY_CODE"].map(dict(zip(le["code"], le[c]))) == df[c]).all() for c in BANK_FLAG_COLS)
    R.add("Bank-grouping flags are a function of the legal entity", bool(flags_ok), "", section=S)
    lst = pd.Series(["|".join(b for b, f in zip(BANK_LABELS, row) if f) or None for row in (df[BANK_FLAG_COLS] == "Y").to_numpy()], index=df.index, dtype=object)
    R.add("USBANKS_LE_LIST agrees with IS_USBANKS / IS_MSBNA / IS_MSPBNA (null iff all N)", bool((lst.fillna("<N>") == df["USBANKS_LE_LIST"].fillna("<N>")).all()), f"{df['USBANKS_LE_LIST'].isna().mean():.1%} null", section=S)
    B = L["buildings"]
    R.add("EVENT_LOCATION deterministic from BUILDING_NAME (location lookup)", bool((df["BUILDING_NAME"].map(dict(zip(B["building"], B["location"]))) == df["EVENT_LOCATION"]).all()), "", section=S)
    R.add("BUILDING_NAME / EMPLOYEE_BUILDING_NAME come from the building lookup", set(df["BUILDING_NAME"]) | set(df["EMPLOYEE_BUILDING_NAME"]) <= set(B["building"]), "", section=S)
    R.add("EMPLOYEE_COUNTRY_NAME deterministic from EMPLOYEE_BUILDING_NAME", bool((df["EMPLOYEE_BUILDING_NAME"].map(dict(zip(B["building"], B["country"]))) == df["EMPLOYEE_COUNTRY_NAME"]).all()), "", section=S)
    ma_ok = (((df["IS_MERGERS_ACQUISITIONS_ASSET"] == "N") & (df["ACQUIRED_ENTITY"] == "NON_ACQUIRED_ENTITY")) |
             ((df["IS_MERGERS_ACQUISITIONS_ASSET"] == "Y") & df["ACQUIRED_ENTITY"].str.startswith("Acquired_Entity_"))).all()
    R.add("ACQUIRED_ENTITY agrees with IS_MERGERS_ACQUISITIONS_ASSET", bool(ma_ok), "", section=S)
    dis = float((df["HAS_CTIRICAL_KBS"] != df["KBS_FLAG_FLAG"]).mean())
    R.add("KBS_FLAG_FLAG consistent with HAS_CTIRICAL_KBS", abs(dis - cfg["entity"]["kbs_flag_disagreement_rate"]) < 0.02, f"{dis:.2%} disagree", section=S)

    # ---------------- compliance & testing ----------------
    S = "Compliance & testing"
    tc = df["TEST_STATUS"] == "Test_Complete"
    R.add("TEST_RESULT null whenever no completed test", bool(df.loc[~tc, "TEST_RESULT"].isna().all()), f"{int(df.loc[~tc, 'TEST_RESULT'].notna().sum())} violations", section=S)
    R.add("Test_Complete rows nearly always carry Pass/Fail", float(df.loc[tc, "TEST_RESULT"].notna().mean()) >= 0.98, f"{df.loc[tc, 'TEST_RESULT'].notna().mean():.2%}", section=S)
    rk = (df["COMPLIANCE_STATUS"] + "|" + df["TEST_STATUS"] + "|" + df["TEST_RESULT"].fillna("None")).to_numpy()
    tbl = RU["reason_table"]
    bad_key = [k for k in set(rk) if k not in tbl]
    R.add("(COMPLIANCE_STATUS, TEST_STATUS, TEST_RESULT) combinations are all permitted", not bad_key, bad_key[:5] or f"{len(set(rk))} combinations used", section=S)
    bad_reason = sum(1 for k, r in zip(rk, df["COMPLIANCE_REASON"]) if k in tbl and r not in tbl[k])
    R.add("COMPLIANCE_REASON consistent with COMPLIANCE_STATUS and TEST_STATUS", bad_reason == 0, f"{bad_reason} violations", section=S)
    R.add("No-test rows carry a synthetic no-test reason or pending/NA reason (never a 'Test_Failed'/'Requirements_Met' reason)",
          bool(~df.loc[df["TEST_STATUS"] == "No_Test", "COMPLIANCE_REASON"].isin(["Test_Failed", "Requirements_Met", "Controls_Verified"]).any()), "", section=S)
    ex = df["TEST_STATUS"] == "Exempt"
    R.add("EXEMPTION_LEVEL_1 usually populated when Exempt", float(df.loc[ex, "EXEMPTION_LEVEL_1"].notna().mean()) >= 0.90, f"{df.loc[ex, 'EXEMPTION_LEVEL_1'].notna().mean():.1%}", section=S)
    R.add("EXEMPTION_LEVEL_1 mostly blank otherwise", float(df.loc[~ex, "EXEMPTION_LEVEL_1"].notna().mean()) <= 0.05, f"{df.loc[~ex, 'EXEMPTION_LEVEL_1'].notna().mean():.1%} populated", section=S)
    both = df["RFB"].notna() & df["TOTAL_RFB"].notna()
    R.add("TOTAL_RFB >= RFB where both numeric", bool((df.loc[both, "TOTAL_RFB"] >= df.loc[both, "RFB"]).all()), f"{int((df.loc[both,'TOTAL_RFB'] < df.loc[both,'RFB']).sum())} violations", section=S)
    comp = df["COMPLIANCE_STATUS"] == "Compliant"
    R.add("RFB normally zero for compliant rows", float((df.loc[comp, "RFB"].dropna() == 0).mean()) >= 0.85, f"{(df.loc[comp, 'RFB'].dropna() == 0).mean():.1%} zero", "WARN", S)
    r_nc = df.loc[df["COMPLIANCE_STATUS"] == "Non_Compliant", "SYSTEM_RTC"].astype(float).mean()
    r_c = df.loc[comp, "SYSTEM_RTC"].astype(float).mean()
    R.add("SYSTEM_RTC=1 more likely for non-compliant than compliant rows", r_nc > r_c, f"{r_nc:.1%} vs {r_c:.1%}", section=S)
    R.add("IS_NUMERATOR <= IS_DENOMINATOR", bool((df["IS_NUMERATOR"] <= df["IS_DENOMINATOR"]).all()), "", section=S)
    var = df["METRIC_ID"].map(dict(zip(L["metrics"]["METRIC_ID"], L["metrics"]["denominator_variant"])))
    den_exp = np.where(var == "A", df["COMPLIANCE_STATUS"].isin(RU["denominator_variants"]["A"]), df["COMPLIANCE_STATUS"].isin(RU["denominator_variants"]["B"])).astype(int)
    num_exp = (df["COMPLIANCE_STATUS"].isin(RU["numerator_statuses"]).to_numpy() & (den_exp == 1)).astype(int)
    R.add("IS_DENOMINATOR / IS_NUMERATOR follow the provisional metric-variant rule", bool((df["IS_DENOMINATOR"].astype(int).to_numpy() == den_exp).all() and (df["IS_NUMERATOR"].astype(int).to_numpy() == num_exp).all()), "provisional rule, not a client definition", section=S)

    # ---------------- grain & duplicates ----------------
    S = "Grain & duplicates"
    dd = P["duplicates"]
    R.add("Candidate key (EON_ID, METRIC_ID, METRIC_DATE) is unique", dd["EON_ID+METRIC_ID+METRIC_DATE (candidate row key)"] == 0, str(dd["EON_ID+METRIC_ID+METRIC_DATE (candidate row key)"]), section=S)
    R.add("No fully duplicated rows", dd["full_row"] == 0, str(dd["full_row"]), section=S)
    R.add("METRIC_ID values all come from the metric catalogue", set(df["METRIC_ID"]) <= set(L["metrics"]["METRIC_ID"]), f"{df['METRIC_ID'].nunique()} used of {len(L['metrics'])}", section=S)
    mrow = df.groupby("METRIC_ID").size()
    R.add("METRIC_ID repeats across applications and periods (not a row key)", bool((df.groupby("METRIC_ID")["EON_ID"].nunique() > 1).all() and (df.groupby("METRIC_ID")["METRIC_DATE"].nunique() > 1).all()), f"rows/metric min {mrow.min()} max {mrow.max()}", section=S)

    # ---------------- longitudinal ----------------
    S = "Longitudinal behaviour"
    er = P["entity_repetition"]
    R.add("Distinct EON_ID within target range", V["min_distinct_entities"] <= er["distinct_eon_id"] <= V["max_distinct_entities"], str(er["distinct_eon_id"]), section=S)
    R.add("Meaningful share of applications observed in 2+ periods", er["share_eon_with_2plus_months"] >= V["min_share_entities_2plus_months"], f"{er['share_eon_with_2plus_months']:.1%}", section=S)
    R.add("Meaningful share of applications observed in 6+ periods", er["share_eon_with_6plus_months"] >= V["min_share_entities_6plus_months"], f"{er['share_eon_with_6plus_months']:.1%}", section=S)
    R.add("Dataset is not a full Cartesian grid (sparse history present)", er["share_eon_with_all_months"] < 0.6 and er["share_eon_single_observation"] > 0, f"{er['share_eon_with_all_months']:.1%} fully observed, {er['share_eon_single_observation']:.1%} single observation", section=S)
    R.add("Heavy-tailed observations per application (top 10% of apps hold well above 10% of rows)", er["top_decile_eon_row_share"] > 0.2, f"{er['top_decile_eon_row_share']:.1%}", "WARN", S)
    per_rows = [p["rows"] for p in P["periods"]]
    R.add("Every reporting period has data", min(per_rows) > 0, f"min {min(per_rows)} max {max(per_rows)} rows/period", section=S)
    tr = P["transitions"]
    R.add("Month-to-month new non-compliance observed", tr["new_non_compliance"] > 0, str(tr["new_non_compliance"]), section=S)
    R.add("Month-to-month remediation (non-compliance resolved) observed", tr["resolved_non_compliance"] > 0, str(tr["resolved_non_compliance"]), section=S)
    rates = [p["provisional_compliance_rate"] for p in P["periods"] if p["provisional_compliance_rate"] is not None]
    R.add("Provisional compliance rate varies across months (trend demonstrable)", (max(rates) - min(rates)) >= 0.01, f"range {min(rates):.3f}-{max(rates):.3f}", "WARN", S)

    # ---------------- scenarios ----------------
    S = "Scenarios"
    sc = P["scenarios"]
    R.add("All configured scenarios are present", set(sc) == set(cfg["scenarios"]["fractions"]), f"{len(sc)} scenarios", section=S)

    def g(name, key):
        return sc.get(name, {}).get(key)
    if "consistently_compliant" in sc:
        R.add("consistently_compliant: Non_Compliant share <= 15%", g("consistently_compliant", "non_compliant_share") <= 0.15, g("consistently_compliant", "non_compliant_share"), "WARN", S)
    if "persistently_noncompliant" in sc:
        R.add("persistently_noncompliant: Non_Compliant share >= 60%", g("persistently_noncompliant", "non_compliant_share") >= 0.60, g("persistently_noncompliant", "non_compliant_share"), "WARN", S)
    if "deteriorating" in sc:
        a, b = g("deteriorating", "nc_share_before_switch"), g("deteriorating", "nc_share_after_switch")
        R.add("deteriorating: Non_Compliant share rises after the switch month", b - a >= 0.30, f"{a:.2f} -> {b:.2f}", "WARN", S)
    if "improving_after_remediation" in sc:
        a, b = g("improving_after_remediation", "nc_share_before_switch"), g("improving_after_remediation", "nc_share_after_switch")
        R.add("improving_after_remediation: Non_Compliant share falls after the switch month", a - b >= 0.30, f"{a:.2f} -> {b:.2f}", "WARN", S)
    if "no_completed_tests" in sc:
        R.add("no_completed_tests: zero Test_Complete rows", g("no_completed_tests", "test_complete_share") == 0.0, g("no_completed_tests", "test_complete_share"), section=S)
    if "pending_tests" in sc:
        R.add("pending_tests: Test_Pending dominates", g("pending_tests", "test_pending_share") >= 0.60, g("pending_tests", "test_pending_share"), "WARN", S)
    if "exempt" in sc:
        R.add("exempt: Exempt dominates", g("exempt", "exempt_share") >= 0.60, g("exempt", "exempt_share"), "WARN", S)
    rv = P["risk_vs_compliance"]
    R.add("No artificial risk/compliance coupling: each risk code has a mixed Non_Compliant share (5%-80%)",
          all(0.05 <= v["non_compliant_share"] <= 0.80 for v in rv.values()), {k: v["non_compliant_share"] for k, v in rv.items()}, section=S)
    R.add("Failed completed tests occur in every asset-risk code", all((v["fail_share_of_completed"] or 0) > 0 for v in rv.values()), "", section=S)

    # ---------------- disclosure ----------------
    S = "Privacy / disclosure"
    scan = disclosure_scan(df, cfg, L)
    R.add("Disclosure scan: no emails, deny-listed firm/bank terms, real-name matches, null-like strings or out-of-shape values", scan["status"] == "PASS",
          f"{scan['n_findings']} findings over {scan['distinct_values_scanned']:,} distinct values in {scan['columns_scanned']} columns {scan['by_check'] or ''}", section=S)
    R.add("Disclosure scanner self-test detects planted violations", disclosure_scan_selftest(cfg, L), "", section=S)
    P["disclosure_scan"] = scan
    return R.rows, P


# ======================================================================================
# 10. Golden questions (reproducible SQL, verified against pandas)
# ======================================================================================
GOLDEN_TABLE = "SYNTHETIC_ENTERPRISE_DATA"


def build_golden_questions(df: pd.DataFrame) -> list:
    d = df["REPORTING_MONTHEND_DATE"]
    latest = d.max()
    months = sorted(d.unique())
    prev = months[-2]
    ctx = {"LATEST": latest.strftime("%Y-%m-%d"), "PREV": pd.Timestamp(prev).strftime("%Y-%m-%d"), "NM": len(months), "T": GOLDEN_TABLE}
    tmp = df.copy()
    for c in DATE_COLS:
        tmp[c] = tmp[c].dt.strftime("%Y-%m-%d")
    for c in INT_COLS:
        tmp[c] = tmp[c].astype(object).where(tmp[c].notna(), None)
    con = sqlite3.connect(":memory:")
    tmp.astype(object).where(tmp.notna(), None).to_sql(GOLDEN_TABLE, con, index=False)
    lat = df[d == latest]
    prv = df[d == prev]

    def p_rate():
        g = df.groupby("REPORTING_MONTHEND_DATE")[["IS_NUMERATOR", "IS_DENOMINATOR"]].sum()
        return [[i.strftime("%Y-%m-%d"), round(r.IS_NUMERATOR / r.IS_DENOMINATOR, 4)] for i, r in g.iterrows()]

    def p_fail():
        x = df[(df.TEST_STATUS == "Test_Complete") & (df.TEST_RESULT == "Fail")]
        return [[i.strftime("%Y-%m-%d"), int(v)] for i, v in x.groupby("REPORTING_MONTHEND_DATE").size().items()]

    def p_topsd():
        x = lat[lat.COMPLIANCE_STATUS == "Non_Compliant"].groupby("SUPER_DIVISION")["EON_ID"].nunique().reset_index()
        x = x.sort_values(["EON_ID", "SUPER_DIVISION"], ascending=[False, True]).head(5)
        return x.values.tolist()

    def p_new():
        cur = set(lat[lat.COMPLIANCE_STATUS == "Non_Compliant"].EON_ID)
        pa, pn = set(prv.EON_ID), set(prv[prv.COMPLIANCE_STATUS == "Non_Compliant"].EON_ID)
        return [[len([e for e in cur if e in pa and e not in pn])]]

    def p_le():
        x = lat.groupby("LEGAL_ENTITY_NAME")["EON_ID"].nunique().reset_index().sort_values(["EON_ID", "LEGAL_ENTITY_NAME"], ascending=[False, True]).head(5)
        return x.values.tolist()

    def p_owner():
        x = lat.groupby(["PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"])["EON_ID"].nunique().reset_index()
        x = x.sort_values(["EON_ID", "PRIMARY_BUS_FIRST_NAME", "PRIMARY_BUS_LAST_NAME"], ascending=[False, True, True]).head(5)
        return x.values.tolist()

    def p_rfb():
        x = lat.groupby("COMPLIANCE_STATUS").agg(a=("RFB", "mean"), n=("RFB", "size")).reset_index().sort_values("COMPLIANCE_STATUS")
        return [[r.COMPLIANCE_STATUS, round(float(r.a), 3), int(r.n)] for r in x.itertuples()]

    def p_riskfail():
        x = df[(df.TEST_STATUS == "Test_Complete") & df.TEST_RESULT.notna()]
        g = x.groupby("ASSET_RISK_RATING_2").agg(n=("TEST_RESULT", "size"), f=("TEST_RESULT", lambda s: (s == "Fail").mean())).reset_index()
        return [[r.ASSET_RISK_RATING_2, int(r.n), round(float(r.f), 4)] for r in g.itertuples()]

    qs = [
        dict(id="Q01", status="Unambiguous", question=f"How many distinct applications reported in {latest:%B %Y}?",
             grain="Distinct EON_ID within the month filter.",
             sql="SELECT COUNT(DISTINCT EON_ID) AS DISTINCT_APPLICATIONS FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}'",
             pandas=lambda: [[int(lat.EON_ID.nunique())]]),
        dict(id="Q02", status="Unambiguous", question=f"How many applications reported in all {len(months)} periods?",
             grain="Distinct reporting months per EON_ID.",
             sql="SELECT COUNT(*) AS APPLICATIONS_REPORTING_ALL_PERIODS FROM (SELECT EON_ID FROM {T} GROUP BY EON_ID HAVING COUNT(DISTINCT REPORTING_MONTHEND_DATE) = {NM}) X",
             pandas=lambda: [[int((df.groupby("EON_ID")["REPORTING_MONTHEND_DATE"].nunique() == len(months)).sum())]]),
        dict(id="Q03", status="Unambiguous", question=f"How many rows are in each COMPLIANCE_STATUS in {latest:%B %Y}?",
             grain="Row counts (one row = app x metric x month), not application counts.",
             sql="SELECT COMPLIANCE_STATUS, COUNT(*) AS ROW_COUNT FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' GROUP BY COMPLIANCE_STATUS ORDER BY ROW_COUNT DESC, COMPLIANCE_STATUS",
             pandas=lambda: [[k, int(v)] for k, v in sorted(lat.COMPLIANCE_STATUS.value_counts().items(), key=lambda kv: (-kv[1], kv[0]))]),
        dict(id="Q04", status="PROVISIONAL (numerator/denominator rule is a generator assumption)", question="What is the provisional compliance rate by reporting month?",
             grain="SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR) at row grain across all metrics; metric variants A/B differ in denominator scope.",
             sql="SELECT REPORTING_MONTHEND_DATE, ROUND(1.0 * SUM(IS_NUMERATOR) / NULLIF(SUM(IS_DENOMINATOR), 0), 4) AS PROVISIONAL_COMPLIANCE_RATE FROM {T} GROUP BY REPORTING_MONTHEND_DATE ORDER BY REPORTING_MONTHEND_DATE",
             pandas=p_rate),
        dict(id="Q05", status="Unambiguous", question="How many completed tests failed in each month?",
             grain="Row counts where TEST_STATUS = 'Test_Complete' and TEST_RESULT = 'Fail'.",
             sql="SELECT REPORTING_MONTHEND_DATE, COUNT(*) AS FAILED_TEST_ROWS FROM {T} WHERE TEST_STATUS = 'Test_Complete' AND TEST_RESULT = 'Fail' GROUP BY REPORTING_MONTHEND_DATE ORDER BY REPORTING_MONTHEND_DATE",
             pandas=p_fail),
        dict(id="Q06", status="Unambiguous (an application counts once if any of its rows is Non_Compliant)", question=f"Which 5 SUPER_DIVISIONs have the most non-compliant applications in {latest:%B %Y}?",
             grain="COUNT(DISTINCT EON_ID) with at least one Non_Compliant row in the month.",
             sql="SELECT SUPER_DIVISION, COUNT(DISTINCT EON_ID) AS NON_COMPLIANT_APPLICATIONS FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' AND COMPLIANCE_STATUS = 'Non_Compliant' GROUP BY SUPER_DIVISION ORDER BY NON_COMPLIANT_APPLICATIONS DESC, SUPER_DIVISION LIMIT 5",
             pandas=p_topsd),
        dict(id="Q07", status="PROVISIONAL (definition of 'newly non-compliant' is an analyst assumption)", question=f"How many applications became non-compliant in {latest:%B %Y}?",
             grain="App has a Non_Compliant row in the latest month, was reported in the previous month, and had no Non_Compliant row then.",
             sql="SELECT COUNT(*) AS NEWLY_NON_COMPLIANT_APPLICATIONS FROM (SELECT DISTINCT EON_ID FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' AND COMPLIANCE_STATUS = 'Non_Compliant') C WHERE C.EON_ID IN (SELECT EON_ID FROM {T} WHERE REPORTING_MONTHEND_DATE = '{PREV}') AND C.EON_ID NOT IN (SELECT EON_ID FROM {T} WHERE REPORTING_MONTHEND_DATE = '{PREV}' AND COMPLIANCE_STATUS = 'Non_Compliant')",
             pandas=p_new),
        dict(id="Q08", status="Unambiguous", question=f"Which 5 legal entities hold the most distinct applications in {latest:%B %Y}?",
             grain="COUNT(DISTINCT EON_ID) by LEGAL_ENTITY_NAME for the month.",
             sql="SELECT LEGAL_ENTITY_NAME, COUNT(DISTINCT EON_ID) AS APPLICATIONS FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' GROUP BY LEGAL_ENTITY_NAME ORDER BY APPLICATIONS DESC, LEGAL_ENTITY_NAME LIMIT 5",
             pandas=p_le),
        dict(id="Q09", status="Unambiguous", question=f"How many M&A-associated applications have a non-compliant row in {latest:%B %Y}?",
             grain="COUNT(DISTINCT EON_ID) with IS_MERGERS_ACQUISITIONS_ASSET = 'Y' and a Non_Compliant row in the month.",
             sql="SELECT COUNT(DISTINCT EON_ID) AS MA_NON_COMPLIANT_APPLICATIONS FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' AND IS_MERGERS_ACQUISITIONS_ASSET = 'Y' AND COMPLIANCE_STATUS = 'Non_Compliant'",
             pandas=lambda: [[int(lat[(lat.IS_MERGERS_ACQUISITIONS_ASSET == "Y") & (lat.COMPLIANCE_STATUS == "Non_Compliant")].EON_ID.nunique())]]),
        dict(id="Q10", status="Unambiguous", question=f"Which 5 primary business owners (fictional) own the most applications in {latest:%B %Y}?",
             grain="COUNT(DISTINCT EON_ID) by (PRIMARY_BUS_FIRST_NAME, PRIMARY_BUS_LAST_NAME) for the month.",
             sql="SELECT PRIMARY_BUS_FIRST_NAME, PRIMARY_BUS_LAST_NAME, COUNT(DISTINCT EON_ID) AS APPLICATIONS FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' GROUP BY PRIMARY_BUS_FIRST_NAME, PRIMARY_BUS_LAST_NAME ORDER BY APPLICATIONS DESC, PRIMARY_BUS_FIRST_NAME, PRIMARY_BUS_LAST_NAME LIMIT 5",
             pandas=p_owner),
        dict(id="Q11", status="PROVISIONAL (RFB semantics are a generator assumption)", question=f"What is the average RFB per COMPLIANCE_STATUS in {latest:%B %Y}?",
             grain="AVG over rows with non-null RFB (row grain); row counts include null-RFB rows.",
             sql="SELECT COMPLIANCE_STATUS, ROUND(AVG(RFB), 3) AS AVG_RFB, COUNT(*) AS ROW_COUNT FROM {T} WHERE REPORTING_MONTHEND_DATE = '{LATEST}' GROUP BY COMPLIANCE_STATUS ORDER BY COMPLIANCE_STATUS",
             pandas=p_rfb),
        dict(id="Q12", status="PROVISIONAL (risk-code severity direction is not defined by the sources)", question="What share of completed tests failed, by ASSET_RISK_RATING_2 (all months)?",
             grain="Rows with TEST_STATUS = 'Test_Complete' and a non-null TEST_RESULT.",
             sql="SELECT ASSET_RISK_RATING_2, COUNT(*) AS COMPLETED_TESTS, ROUND(1.0 * SUM(CASE WHEN TEST_RESULT = 'Fail' THEN 1 ELSE 0 END) / COUNT(*), 4) AS FAIL_SHARE FROM {T} WHERE TEST_STATUS = 'Test_Complete' AND TEST_RESULT IS NOT NULL GROUP BY ASSET_RISK_RATING_2 ORDER BY ASSET_RISK_RATING_2",
             pandas=p_riskfail),
    ]

    def same(a, b):
        if len(a) != len(b):
            return False
        for ra, rb in zip(a, b):
            if len(ra) != len(rb):
                return False
            for x, y in zip(ra, rb):
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    if abs(float(x) - float(y)) > 1.5e-3:
                        return False
                elif str(x) != str(y):
                    return False
        return True

    out = []
    for q in qs:
        sql = q["sql"].format(**ctx)
        cur = con.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        expected = [[_json_cell(v) for v in r] for r in rows]
        try:
            verified = same(rows, q["pandas"]())
        except Exception as exc:  # pragma: no cover
            verified = False
        out.append({"id": q["id"], "question": q["question"], "status": q["status"], "grain": q["grain"], "sql": sql,
                    "columns": cols, "expected": expected, "verified_sql_vs_pandas": bool(verified)})
    con.close()
    return out


def _json_cell(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


# ======================================================================================
# 11. Assumptions register content
# ======================================================================================
ASSUMPTIONS = [
    # (id, area, decision / assumption, status, config key)
    ("A01", "Source handling", "Data_Dictionary_1.xlsx is the primary reference for column names, types, examples, nullability, vocabularies and relationships; the Word prompt supplies counts, column order, privacy rules, relationships and validation requirements. Dictionary has one visible worksheet (no hidden sheets, comments or defined names); its 57 columns are in exactly the same order as Part 1 of the Word prompt.", "Source-derived", "-"),
    ("A02", "Source gap", "Part 3 of the Word prompt is truncated at 'PRIMARY_BUS_FIRST_NAME/LAST_NAME and PRIMARY_IT_FIRST_NAME/LAST_NAME must be stable fictional person pairs, generally ...' ('continuation not visible'). The missing text was NOT invented. Interpretation taken from the dictionary ('stable pair for an EON_ID'): a (first,last) pair is a single fictional person and is stable within EON_ID except for a controlled owner-change rate.", "Gap in source", "change_rates.bus_owner / it_owner"),
    ("A03", "Source conflict", "ACQUIRED_ENTITY: the Word prompt lists acquisition fields among columns with moderate/high null rates, but the dictionary example is NON_ACQUIRED_ENTITY and its rule says the column 'must agree with IS_MERGERS_ACQUISITIONS_ASSET'. Decision: dictionary governs - ACQUIRED_ENTITY is never null; 'N' => NON_ACQUIRED_ENTITY, 'Y' => a fictional Acquired_Entity_NN.", "Conflict resolved (dictionary wins)", "entity.ma_rate"),
    ("A04", "Source conflict", "Identifier formats: the Word prompt asks for 'unrelated ranges and prefixes'; the dictionary's synthetic examples use the prefixes EON / M / CC / LE and the grn:/synthetic/domain/ URI. Decision: keep the dictionary prefixes so the data loads into the planned schema unchanged, but draw all numeric parts from ranges disjoint from the dictionary examples. Prefixes are configurable; the disclosure scan range-checks them. If any prefix is considered proprietary, change id_prefixes and re-run.", "Conflict resolved (compromise)", "id_prefixes, id_ranges"),
    ("A05", "Source conflict", "Naming conventions: the Word prompt lists neutral patterns such as Person_0001 and Division_01; the dictionary shows hierarchical labels (BU_Division_04_03, Department_07_01_01_01) and syllable-style person names (Quinve, LiaHa). Decision: dictionary label patterns are used for organisation fields; people are built from internal syllable lists (both sources allow this) and checked against a real-name deny-list.", "Conflict resolved", "-"),
    ("A06", "Source gap", "Neither file supplies real-data distributions. Every probability vector is a plausible enterprise-style assumption (dominant / medium / long-tail categories). The output must NOT be described as statistically equivalent to the client's data; it only reproduces schema, relationships and qualitative shapes.", "Gap in source", "entity.*, scenarios.*, rules.*"),
    ("A07", "Privacy", "Legacy column names IS_USBANKS, IS_MSBNA, IS_MSPBNA are kept verbatim. Their values are generic Y/N and USBANKS_LE_LIST uses BANK_A|BANK_B|BANK_C. Mapping IS_USBANKS->BANK_A, IS_MSBNA->BANK_B, IS_MSPBNA->BANK_C is a generator convention, not a statement about any institution.", "Provisional", "entity.bank_flag_rates"),
    ("A08", "Privacy", "Disclosure scan = e-mail/URL regex + deny-list of firm/bank/brand tokens + real first/last-name lists + per-column shape whitelist + ID-range check. The embedded deny-lists are NOT exhaustive; extend validation.extra_forbidden_terms for site-specific terms.", "Provisional", "validation.extra_forbidden_terms"),
    ("A09", "Schema", "HAS_CTIRICAL_KBS and KBS_FLAG_FLAG spellings preserved. KBS_FLAG_FLAG equals HAS_CTIRICAL_KBS on every row by default ('generated consistently'); a disagreement rate can be configured.", "Provisional", "entity.kbs_flag_disagreement_rate"),
    ("B01", "Row grain", "One row = one observation of one METRIC_ID for one application (EON_ID) at one month-end. Candidate key (EON_ID, METRIC_ID, METRIC_DATE) is unique. METRIC_ID is NOT a row key and repeats across applications and months. The true aggregation grain of every client METRIC_ID is unknown.", "Provisional", "-"),
    ("B02", "Cardinality", "1,500 synthetic applications (EON_ID), inside the requested 1,000-2,000 band. Each has a fixed APPLICATION_NAME and GRN.", "Provisional", "cardinality.n_entities"),
    ("B03", "Cardinality", "24 metrics in 6 families. Each application has a Zipf-weighted primary metric (72% of apps have one metric, 22% two, 6% three; secondary metrics come from the primary's family 70% of the time). Metrics differ only by denominator-scope variant (A/B) and a small failure-probability offset; they carry no business meaning.", "Provisional", "cardinality.n_metrics, observations.*"),
    ("B04", "Reporting period", "12 consecutive month-ends ending 2026-10-31 (Nov-2025 .. Oct-2026). Date span, month count and METRIC_DATE_TYPE vocabulary are configurable; the dictionary does not override this default.", "Provisional", "reporting.*"),
    ("B05", "Longitudinal sparsity", "The fixed 11,399-row budget is spread over applications with a heavy-tailed number of observations (lognormal, then capped by metric x month capacity). Each application is observed inside a contiguous window (50% anchored to the latest month = still reporting, 15% anchored to the first month, 35% random) with occasional gaps. The result is intentionally sparse, not a Cartesian grid. Side effect: the reporting population grows over the window (rows per month rise from roughly 700 to roughly 1,100) because windows are anchored towards the latest month; absolute counts therefore trend upwards by construction.", "Provisional", "observations.*"),
    ("C01", "Compliance / test rules", "COMPLIANCE_STATUS, COMPLIANCE_REASON, TEST_STATUS, TEST_RESULT, EXEMPTION_LEVEL_1, SYSTEM_RTC, RFB, TOTAL_RFB, IS_NUMERATOR and IS_DENOMINATOR are generated jointly from the rule tables in rules.* conditioned on scenario, month and metric. Reason vocabulary (apart from Requirements_Met from the dictionary example) is invented and keyed by COMPLIANCE_STATUS|TEST_STATUS|TEST_RESULT.", "Provisional", "rules.*"),
    ("C02", "Compliance / test rules", "TEST_RESULT is Pass/Fail only when TEST_STATUS = Test_Complete (0.8% of those rows have a missing result as a deliberate data-quality gap); it is null for Test_Pending, Exempt and No_Test. Tests that fail do not always give Non_Compliant (and passes not always Compliant) so outcomes are not perfectly correlated.", "Provisional", "missingness.TEST_RESULT_when_test_complete"),
    ("C03", "Numerator / denominator", "NOT a confirmed business rule. Metric variant A: denominator = Compliant + Non_Compliant; variant B: also includes Pending; Not_Applicable is never in a denominator; numerator = Compliant rows inside the denominator. The sources only say 'interpretation depends on the metric definition'.", "Provisional", "rules.denominator_variants, rules.numerator_statuses"),
    ("C04", "SYSTEM_RTC", "Meaning is not defined in the sources beyond 'more likely for non-compliant records'. Modelled as a Bernoulli by COMPLIANCE_STATUS (Non_Compliant 35%, Pending 10%, Compliant 6%, Not_Applicable 4%).", "Provisional", "rules.system_rtc_prob_by_status"),
    ("C05", "RFB / TOTAL_RFB", "Interpretation is not defined in the sources. RFB is a row-level zero-inflated count dependent on COMPLIANCE_STATUS (normally zero when compliant). TOTAL_RFB = sum of RFB over all rows of the same application-month + Poisson 'other findings', repeated on every row of that application-month, hence TOTAL_RFB >= RFB. 1% of each column is null.", "Provisional", "rules.rfb, rules.total_rfb_extra, missingness.RFB/TOTAL_RFB"),
    ("C06", "RTO_CHANGE_DATE", "Entity-level history: 30% of applications have a change before the window; applications whose APPLICATION_RTO band changes get an in-window change date inside the month the band changes; 6% get an in-window date without a band change. A row shows the latest change date on/before its METRIC_DATE, else null (so it is never later than METRIC_DATE).", "Provisional", "entity.rto_history_pre_window_share, entity.rto_extra_in_window_date_share"),
    ("C07", "Exemptions", "EXEMPTION_LEVEL_1 is populated for ~97% of Exempt rows (85% reuse the application's preferred Exemption_NN) and for ~2% of other rows ('usually populated when Exempt; otherwise often blank').", "Provisional", "missingness.EXEMPTION_*"),
    ("D01", "Tier & risk direction", "APPLICATION_TIER (1-4), APPLICATION_RTO bands and the P/A/C/I risk codes are generated from a shared latent factor so that they co-move NUMERICALLY (a higher code tends to accompany higher codes elsewhere). The sources do not say whether tier 1 or tier 4, or P1 or P4, is more critical/severe, and no severity direction is asserted or implied.", "Provisional (no severity semantics)", "entity.latent_loading"),
    ("D02", "Risk codes", "ASSET_RISK_RATING_2 (P1-P4) is approximately the rounded mean of the three ARR component codes plus noise. That is a generator device to look coherent, not a client formula; the consuming team defines the real meaning.", "Provisional", "entity.p_code_noise_sd"),
    ("D03", "Risk vs compliance", "Risk attributes are generated independently of the compliance scenario, so high-risk applications are not systematically non-compliant and failed tests occur across all risk codes. The validation step checks that no risk code is all/none non-compliant.", "Provisional", "-"),
    ("E01", "Organisation", "Two independent four-level hierarchies. Each hierarchy-2 department rolls up to exactly one hierarchy-1 (BU_) department via a fixed mapping. ORG_GROUP_TYPE is DEPARTMENT for 88% of applications (both department columns populated) and SUPER_DEPARTMENT for 12% (both department columns null). BUS_ORG_LG_NM is Business_Org_ + the suffix of the department (or super-department).", "Provisional", "cardinality.org1/org2, entity.super_department_level_rate"),
    ("E02", "Cost centres", "Each cost centre belongs to exactly one department; an application's cost centre always belongs to its department. A reorganisation moves an application to a new department, hierarchy path and cost centre together.", "Provisional", "cardinality.n_cost_centers, change_rates.reorg/cost_center"),
    ("E03", "Legal entities", "Legal entities carry the three bank-grouping flags (12% belong to none, giving a null USBANKS_LE_LIST). Applications choose legal entities with a division-specific Zipf mix.", "Provisional", "entity.legal_entity_no_bank_rate"),
    ("E04", "Owners & locations", "Owners are fictional people (unique first+last pair) pooled per super-division and drawn Zipf-weighted. EMPLOYEE_BUILDING_NAME is the business owner's building (person attribute) and EMPLOYEE_COUNTRY_NAME follows from it. BUILDING_NAME follows the owner's building 60% of the time. EVENT_LOCATION is a fixed function of BUILDING_NAME.", "Provisional", "zipf.owner, entity.building_follow_owner_prob"),
    ("F01", "Stability", "Each controlled-change group (tier, RTO band, lifecycle, risk codes, business owner, IT owner, reorganisation, cost centre, legal entity, building) changes at most once per application, with the stated per-application probability (1.5%-5%), at a random observed month. Among applications with 2+ rows the OBSERVED change share is close to the configured probability (sampling noise of roughly +/-1 percentage point; a change is only visible if the application has a row at or after the change month, and single-row applications cannot show change at all). APPLICATION_NAME, GRN, EON_ID, M&A fields and the critical-KBS flags never change.", "Provisional", "change_rates.*"),
    ("F02", "Lifecycle change", "A lifecycle change advances one phase (Planning > Development > Implementation > Production > Retirement); Retirement does not change.", "Provisional", "-"),
    ("G01", "Aggregation rule", "Counting applications: COUNT(DISTINCT EON_ID) inside the reporting-month filter. Counting rows is not counting applications (an application can have several metric rows per month).", "Documented rule", "-"),
    ("G02", "Aggregation rule", "Rate-type measures: SUM(IS_NUMERATOR) / SUM(IS_DENOMINATOR) at row grain. Variants A and B have different scopes, so filter or group by METRIC_ID when comparing rates across metrics.", "Documented rule (provisional semantics)", "-"),
    ("G03", "Aggregation rule", "Application-level attributes are stable except for the controlled changes; for a single month use the row values in that month, for multi-month roll-ups take the latest reporting month per EON_ID (deduplicate on EON_ID + REPORTING_MONTHEND_DATE).", "Documented rule", "-"),
    ("G04", "Aggregation rule", "Do not SUM TOTAL_RFB across rows: it repeats for every metric row of the same application-month. Use MAX(TOTAL_RFB) per (EON_ID, REPORTING_MONTHEND_DATE) before aggregating.", "Documented rule", "-"),
    ("G05", "Aggregation rule", "Organisation / legal-entity contributions: report both row counts and distinct-application counts - they differ because of the multi-metric rows.", "Documented rule", "-"),
    ("G06", "Aggregation rule", "Trend demonstrations: use rates or shares (e.g. non-compliant share of rows, provisional compliance rate) rather than absolute row / application counts, because the reporting population grows by construction (B05). The aggregate compliance rate is roughly flat by design; scenario-driven change is visible at application, organisation and legal-entity level.", "Documented rule", "-"),
    ("H01", "Not representable", "Because the confidential source data was not available, no claim is made about real-world prevalence of any category, the true metric catalogue, real tier/risk semantics, real RFB semantics or the true hierarchy sizes.", "Limitation", "-"),
]


def md_table(headers, rows) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v).replace("|", "\\|").replace("\n", " ") for v in r) + " |")
    return "\n".join(out)


def write_assumptions(cfg, path, P):
    lines = ["# Assumptions Register - Metrics Analyzer synthetic dataset", "",
             "Everything below is a **synthetic-generation decision**. Items marked *Provisional* are NOT confirmed client business definitions and are configurable in `PROFILE_CONFIG`.",
             "Unresolved or provisional definitions must be confirmed by the client before they are used as semantic definitions in the Metrics Analyzer / Cortex Agent.", ""]
    for area_title, ids in (("Source handling, conflicts and gaps", "A"), ("Grain, cardinality and reporting period", "B"),
                            ("Compliance, testing and numerical rules", "C"), ("Risk-code and tier interpretation", "D"),
                            ("Organisational hierarchy, legal entity, owners", "E"), ("Entity stability", "F"),
                            ("Aggregation grain and de-duplication rules", "G"), ("Limitations", "H")):
        rows = [(a[0], a[1], a[2], a[3], a[4]) for a in ASSUMPTIONS if a[0].startswith(ids)]
        if rows:
            lines += [f"## {area_title}", "", md_table(["ID", "Area", "Decision / assumption", "Status", "Config key"], rows), ""]
    er = P["entity_repetition"]
    lines += ["## Observed outcomes of the provisional rules (this run)", "",
              f"- Distinct EON_ID: {er['distinct_eon_id']:,}; distinct METRIC_ID: {er['distinct_metric_id']}",
              f"- Observations per EON_ID: median {er['rows_per_eon']['median']:.0f}, mean {er['rows_per_eon']['mean']:.2f}, max {er['rows_per_eon']['max']:.0f}",
              f"- Applications observed in 2+ periods: {er['share_eon_with_2plus_months']:.1%}; in 6+ periods: {er['share_eon_with_6plus_months']:.1%}; in all periods: {er['share_eon_with_all_months']:.1%}",
              "- Scenario shares (entity level): " + ", ".join(f"{k} {v:.1%}" for k, v in P["scenario_entity_shares"].items()), "",
              "These are properties of the generated data only. They are **not** properties of the client's confidential data.", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ======================================================================================
# 12. Output writers
# ======================================================================================
def build_dd_frame(dictionary, P) -> pd.DataFrame:
    rows = []
    for c in EXPECTED_COLUMNS:
        src = None
        if dictionary is not None:
            m = dictionary[dictionary["Column Name"] == c]
            src = m.iloc[0] if len(m) else None
        gen = "date (ISO YYYY-MM-DD)" if c in DATE_COLS else ("nullable integer" if c in INT_COLS else "string")
        info = P["columns"][c]
        rows.append({
            "Column Name": c,
            "Data Type (source)": None if src is None else src["Data Type"],
            "Description (source)": None if src is None else src["Description"],
            "Synthetic Example (source)": None if src is None else str(src["Synthetic Example"]),
            "Rules / Notes (source)": None if src is None else src["Rules / Notes"],
            "Generated Type": gen,
            "Nullable (generated)": "Yes" if c in NULLABLE_COLS else "No",
            "Observed Null Count": info["null_count"], "Observed Null Rate": info["null_rate"], "Observed Distinct": info["distinct"],
            "Generator Rule": GEN_RULES[c],
        })
    return pd.DataFrame(rows)


def build_summary_blocks(cfg, df, P, results, extras) -> list:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for r in results:
        counts[r["status"]] += 1
    er = P["entity_repetition"]
    head = pd.DataFrame([
        ("Overall status", "FAIL" if counts["FAIL"] else ("PASS with warnings" if counts["WARN"] else "PASS")),
        ("Checks PASS / WARN / FAIL", f"{counts['PASS']} / {counts['WARN']} / {counts['FAIL']}"),
        ("Data rows (excl. header)", f"{len(df):,}"), ("Columns", df.shape[1]), ("Random seed", cfg["seed"]),
        ("Reporting periods", f"{df['REPORTING_MONTHEND_DATE'].nunique()} ({df['REPORTING_MONTHEND_DATE'].min():%Y-%m-%d} to {df['REPORTING_MONTHEND_DATE'].max():%Y-%m-%d})"),
        ("Distinct EON_ID", er["distinct_eon_id"]), ("Distinct METRIC_ID", er["distinct_metric_id"]),
        ("Observations per EON_ID (median / mean / max)", f"{er['rows_per_eon']['median']:.0f} / {er['rows_per_eon']['mean']:.2f} / {er['rows_per_eon']['max']:.0f}"),
        ("Disclosure scan", P["disclosure_scan"]["status"]),
        ("CSV SHA-256", extras.get("csv_sha256", "")),
        ("Candidate row key", "EON_ID + METRIC_ID + METRIC_DATE (duplicates: %d)" % P["duplicates"]["EON_ID+METRIC_ID+METRIC_DATE (candidate row key)"]),
        ("Note", "Synthetic data. Statistical properties are generator assumptions, not client-source properties."),
    ], columns=["Item", "Value"])
    checks = pd.DataFrame(results)[["section", "check", "status", "detail"]]
    distinct = pd.DataFrame([(c, P["columns"][c]["distinct"], P["columns"][c]["null_count"], P["columns"][c]["null_rate"]) for c in EXPECTED_COLUMNS],
                            columns=["Column", "Distinct", "Null count", "Null rate"])
    periods = pd.DataFrame(P["periods"])[["date", "rows", "distinct_eon_id", "distinct_metric_id"] + [f"status_{k}" for k in COMPLIANCE_STATUSES] + ["failed_completed_tests", "provisional_compliance_rate"]]
    dist_rows = []
    for c in ("COMPLIANCE_STATUS", "TEST_STATUS", "TEST_RESULT", "APPLICATION_TIER", "LIFECYCLE_PHASE", "ASSET_RISK_RATING_2",
              "ORG_GROUP_TYPE", "IS_MERGERS_ACQUISITIONS_ASSET", "HAS_CTIRICAL_KBS", "APPLICATION_RTO"):
        vc = df[c].value_counts(dropna=False)
        for k, v in vc.items():
            dist_rows.append((c, "<null>" if pd.isna(k) else str(k), int(v), round(float(v / len(df)), 4)))
    dist = pd.DataFrame(dist_rows, columns=["Column", "Value", "Rows", "Share"])
    hist = pd.DataFrame([(int(k), v) for k, v in er["months_per_eon_histogram"].items()], columns=["Reporting periods observed per EON_ID", "Applications"])
    return [("Headline", head), ("Validation checks", checks), ("Rows and distinct counts per reporting period", periods),
            ("Distribution summaries", dist), ("Applications by number of periods observed", hist), ("Distinct counts and missingness by column", distinct)]


def write_xlsx(path, df, dd_df, blocks, assumptions_df):
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"
    with pd.ExcelWriter(path, engine=engine, datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as xw:
        df.to_excel(xw, sheet_name="Data", index=False)
        dd_df.to_excel(xw, sheet_name="Data Dictionary", index=False)
        row = 0
        for title, block in blocks:
            pd.DataFrame([[title]]).to_excel(xw, sheet_name="Validation Summary", startrow=row, index=False, header=False)
            block.to_excel(xw, sheet_name="Validation Summary", startrow=row + 1, index=False)
            row += len(block) + 4
        assumptions_df.to_excel(xw, sheet_name="Assumptions", index=False)
        if engine == "xlsxwriter":
            wb = xw.book
            bold = wb.add_format({"bold": True})
            ws = xw.sheets["Data"]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(df), len(df.columns) - 1)
            for i, c in enumerate(df.columns):
                ws.set_column(i, i, min(max(len(c), 12) + 2, 44))
            ws = xw.sheets["Data Dictionary"]
            ws.freeze_panes(1, 0)
            for i, w in enumerate([26, 22, 55, 28, 55, 20, 12, 12, 12, 12, 70]):
                ws.set_column(i, i, w)
            ws = xw.sheets["Validation Summary"]
            ws.set_column(0, 0, 44)
            ws.set_column(1, 1, 70)
            ws.set_column(2, 3, 18)
            ws.set_column(4, 12, 16)
            r = 0
            for title, block in blocks:
                ws.write(r, 0, title, bold)
                r += len(block) + 4
            ws = xw.sheets["Assumptions"]
            for i, w in enumerate([8, 24, 120, 30, 40]):
                ws.set_column(i, i, w)


def write_metadata(cfg, L, ents, mdir):
    os.makedirs(mdir, exist_ok=True)
    me = L["month_ends"]
    cal = L["calendar"].copy()
    cal["REPORTING_MONTHEND_DATE"] = cal["REPORTING_MONTHEND_DATE"].dt.strftime("%Y-%m-%d")
    cal.to_csv(os.path.join(mdir, "reporting_calendar.csv"), index=False)
    L["buildings"].rename(columns={"building": "BUILDING_NAME", "location": "EVENT_LOCATION", "country": "EMPLOYEE_COUNTRY_NAME"}).to_csv(os.path.join(mdir, "building_location_country_lookup.csv"), index=False)
    L["org2"][["top", "div", "sdp", "dep", "bus_dep", "bus_sdp"]].rename(columns={"top": "SUPER_DIVISION", "div": "DIVISION", "sdp": "SUPER_DEPARTMENT", "dep": "DEPARTMENT", "bus_dep": "BUS_ORG_LG_NM_DEPARTMENT_LEVEL", "bus_sdp": "BUS_ORG_LG_NM_SUPER_DEPARTMENT_LEVEL"}).assign(BU_DEPARTMENT=L["org1"]["dep"].to_numpy()[L["org2_to_org1"]]).to_csv(os.path.join(mdir, "org_hierarchy_2_with_bu_mapping.csv"), index=False)
    L["org1"][["top", "div", "sdp", "dep"]].rename(columns={"top": "BU_SUPER_DIVISION", "div": "BU_DIVISION", "sdp": "BU_SUPER_DEPARTMENT", "dep": "BU_DEPARTMENT"}).to_csv(os.path.join(mdir, "org_hierarchy_1_bu.csv"), index=False)
    cc = L["cost_centers"]
    pd.DataFrame({"COST_CENTER_CODE": cc.code, "COST_CENTER_NAME": cc.name, "DEPARTMENT": L["org2"]["dep"].to_numpy()[cc.leaf.to_numpy()]}).to_csv(os.path.join(mdir, "cost_center_lookup.csv"), index=False)
    L["legal_entities"].rename(columns={"code": "LEGAL_ENTITY_CODE", "name": "LEGAL_ENTITY_NAME", "list": "USBANKS_LE_LIST"}).to_csv(os.path.join(mdir, "legal_entity_lookup.csv"), index=False)
    L["metrics"].drop(columns=["family_idx"]).to_csv(os.path.join(mdir, "metric_catalog.csv"), index=False)
    sd = L["org2"]["top"].drop_duplicates().tolist()
    for nm, key in (("business_owner", "bus_people"), ("it_owner", "it_people")):
        p = L[key]
        pd.DataFrame({"FIRST_NAME": p["first"], "LAST_NAME": p["last"], "HOME_SUPER_DIVISION": [sd[i] for i in p["sd_idx"]],
                      "BUILDING_NAME": L["buildings"]["building"].to_numpy()[p["building_idx"]]}).to_csv(os.path.join(mdir, f"{nm}_lookup.csv"), index=False)
    ev = pd.DataFrame({
        "EON_ID": ents["EON_ID"], "APPLICATION_NAME": ents["APPLICATION_NAME"], "GRN": ents["GRN"], "SCENARIO": ents["scenario"],
        "PRIMARY_METRIC_ID": L["metrics"]["METRIC_ID"].to_numpy()[ents["primary_metric_idx"]],
        "N_OBSERVATIONS": ents["n_obs"], "N_METRICS": ents["n_metrics"],
        "FIRST_OBSERVED_MONTHEND": [me[i].strftime("%Y-%m-%d") for i in ents["first_t"]],
        "LAST_OBSERVED_MONTHEND": [me[i].strftime("%Y-%m-%d") for i in ents["last_t"]],
        "SCENARIO_SWITCH_MONTHEND": [me[i].strftime("%Y-%m-%d") if s in ("deteriorating", "improving_after_remediation") else None for i, s in zip(ents["switch_t"], ents["scenario"])],
    })
    ev.to_csv(os.path.join(mdir, "entity_lookup_with_scenarios.csv"), index=False)
    with open(os.path.join(mdir, "rule_tables.json"), "w", encoding="utf-8") as fh:
        json.dump(to_py({"rules": cfg["rules"], "scenarios": cfg["scenarios"], "change_rates": cfg["change_rates"],
                         "note": "Provisional synthetic rules - not confirmed client business definitions."}), fh, indent=2)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_golden_md(path, golden, cfg, csv_sha):
    lines = ["# Candidate natural-language questions with reproducible SQL", "",
             f"Table: `{GOLDEN_TABLE}` (load `synthetic_enterprise_data.csv` unchanged; dates are ISO text/DATE).",
             "SQL is written in plain ANSI style that runs on both SQLite (used here for verification) and Snowflake.",
             f"Expected answers were computed by executing the SQL on the saved CSV (SHA-256 `{csv_sha[:16]}...`) and independently re-computed with pandas; `Verified` = both agree.",
             "Questions labelled **PROVISIONAL** depend on a generator assumption (see `assumptions_register.md`), not on a confirmed client definition.", ""]
    for q in golden:
        lines += [f"## {q['id']} - {q['question']}", "", f"- **Status:** {q['status']}", f"- **Grain / definition:** {q['grain']}",
                  f"- **Verified (SQL == independent pandas):** {'yes' if q['verified_sql_vs_pandas'] else 'NO'}", "", "```sql", q["sql"], "```", "",
                  "Expected result:", "", md_table(q["columns"], q["expected"]), ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def write_validation_report(path, cfg, P, res_csv, res_xlsx, extras, repairs, dictionary, golden):
    cnt = lambda rs: {k: sum(1 for r in rs if r["status"] == k) for k in ("PASS", "WARN", "FAIL")}  # noqa: E731
    c1, c2 = cnt(res_csv), cnt(res_xlsx)
    ex_rows = extras["checks"]
    c3 = cnt(ex_rows)
    total_fail = c1["FAIL"] + c2["FAIL"] + c3["FAIL"]
    total_warn = c1["WARN"] + c2["WARN"] + c3["WARN"]
    overall = "FAIL" if total_fail else ("PASS with warnings" if total_warn else "PASS")
    n = P["shape"]["rows"]
    L = []
    A = L.append
    A("# Validation Report - Synthetic Enterprise Dataset"); A("")
    A(f"**Overall: {overall}** - CSV checks {c1['PASS']}/{c1['WARN']}/{c1['FAIL']} (PASS/WARN/FAIL), XLSX checks {c2['PASS']}/{c2['WARN']}/{c2['FAIL']}, file-integrity checks {c3['PASS']}/{c3['WARN']}/{c3['FAIL']}.")
    A(""); A("All checks were run against the **saved, re-loaded** CSV and XLSX files (not just the in-memory frame). No sample records are shown in this report.")
    A(""); A("## 1. Run information"); A("")
    A(md_table(["Item", "Value"], [("Generator version", GENERATOR_VERSION), ("Seed", cfg["seed"]), ("Rows (excl. header)", f"{n:,}"),
                                   ("Columns", P["shape"]["columns"]), ("CSV SHA-256", extras["csv_sha256"]),
                                   ("Determinism (2nd full run identical)", extras["deterministic"]),
                                   ("Generation time (s)", extras["seconds"]), ("Dictionary source", None if dictionary is None else f"{dictionary.attrs.get('source_path')} ({len(dictionary)} columns, sheet state {dictionary.attrs.get('sheet_state')})")]))
    A(""); A("Rule repairs applied by `enforce_rules` (safety net; 0 means the generator already produced compliant values):"); A("")
    A(md_table(["Repair", "Rows touched"], list(repairs.items())))
    sections = []
    for r in res_csv:
        if r["section"] not in sections:
            sections.append(r["section"])
    A(""); A("## 2. Schema, row and column counts"); A("")
    A(md_table(["Check", "Status", "Detail"], [(r["check"], r["status"], r["detail"]) for r in res_csv if r["section"] == "Schema"]))
    A(""); A("## 3. Column types, missingness and distinct counts"); A("")
    A(md_table(["Column", "Generated type", "Nullable", "Null count", "Null rate", "Distinct", "Top-1 share"],
               [(c, "date" if c in DATE_COLS else ("Int64" if c in INT_COLS else "string"), "yes" if c in NULLABLE_COLS else "no",
                 P["columns"][c]["null_count"], f"{P['columns'][c]['null_rate']:.2%}", P["columns"][c]["distinct"], f"{P['columns'][c]['top1_share']:.1%}") for c in EXPECTED_COLUMNS]))
    A(""); A("## 4. Top categorical shares (columns with <= 60 distinct values)"); A("")
    rows = []
    for c in EXPECTED_COLUMNS:
        tv = P["columns"][c].get("top_values")
        if tv:
            rows.append((c, P["columns"][c]["distinct"], "; ".join(f"{k} {v:.1%}" for k, v in tv[:4])))
    A(md_table(["Column", "Distinct", "Top values (share of rows)"], rows))
    A(""); A("Long-tail indicator (share of a column's distinct values holding < 1% of rows) for high-cardinality columns:"); A("")
    A(md_table(["Column", "Distinct", "Top-1 share", "Share of values < 1% of rows"],
               [(c, P["columns"][c]["distinct"], f"{P['columns'][c]['top1_share']:.1%}", f"{P['columns'][c]['tail_share_lt_1pct']:.0%}")
                for c in ("EON_ID", "METRIC_ID", "COST_CENTER_CODE", "LEGAL_ENTITY_CODE", "BUILDING_NAME", "DEPARTMENT", "PRIMARY_BUS_LAST_NAME", "EXEMPTION_LEVEL_1")]))
    A(""); A("## 5. Reporting period coverage"); A("")
    A(md_table(["Date", "Rows", "Distinct EON_ID", "Distinct METRIC_ID", "Compliant", "Non_Compliant", "Pending", "Not_Applicable", "Failed tests", "Provisional compliance rate"],
               [(p["date"], p["rows"], p["distinct_eon_id"], p["distinct_metric_id"], p["status_Compliant"], p["status_Non_Compliant"], p["status_Pending"], p["status_Not_Applicable"], p["failed_completed_tests"], p["provisional_compliance_rate"]) for p in P["periods"]]))
    A(""); A(f"Date columns: " + "; ".join(f"{c}: {v['min']} to {v['max']} ({v['distinct']} distinct)" for c, v in P["dates"].items()))
    er = P["entity_repetition"]
    A(""); A("## 6. Entity repetition statistics"); A("")
    A(md_table(["Statistic", "Value"], [("Distinct EON_ID", er["distinct_eon_id"]), ("Distinct METRIC_ID", er["distinct_metric_id"]),
                                         ("Rows per EON_ID (min / p25 / median / mean / p75 / p90 / max)", " / ".join(str(er["rows_per_eon"][k]) for k in ("min", "p25", "median", "mean", "p75", "p90", "max"))),
                                         ("Periods observed per EON_ID (same stats)", " / ".join(str(er["months_per_eon"][k]) for k in ("min", "p25", "median", "mean", "p75", "p90", "max"))),
                                         ("Metrics per EON_ID histogram", er["metrics_per_eon_histogram"]),
                                         ("Share of apps in 2+ / 6+ / all periods", f"{er['share_eon_with_2plus_months']:.1%} / {er['share_eon_with_6plus_months']:.1%} / {er['share_eon_with_all_months']:.1%}"),
                                         ("Share of apps with a single observation", f"{er['share_eon_single_observation']:.1%}"),
                                         ("Top-10% apps' share of rows / largest single app", f"{er['top_decile_eon_row_share']:.1%} / {er['largest_eon_row_share']:.2%}"),
                                         ("Rows per METRIC_ID (min / median / max)", f"{P['metric_repetition']['rows_per_metric']['min']:.0f} / {P['metric_repetition']['rows_per_metric']['median']:.0f} / {P['metric_repetition']['rows_per_metric']['max']:.0f}")]))
    A(""); A("Applications by number of periods observed:"); A("")
    A(md_table(["Periods observed", "Applications"], list(er["months_per_eon_histogram"].items())))
    A(""); A("## 7. Application stability within EON_ID"); A("")
    A(md_table(["Attribute group", "Multi-row apps", "Apps with a change", "Rows off the app's modal value"],
               [(k, v["entities_with_2plus_rows"], f"{v['share_entities_with_change']:.2%}", f"{v['share_rows_off_modal_value']:.2%}") for k, v in P["stability"].items()]))
    A(""); A("Shares are among applications with 2+ rows. Configured change probabilities are per application over the window; observed shares sit close to them (sampling noise about +/-1pp). Single-row applications cannot show change (see assumptions F01).")
    for title, sec in (("8. Hierarchy, lookup and mapping consistency", "Hierarchies & lookups"), ("9. Compliance and testing consistency", "Compliance & testing"),
                       ("10. Keys, nulls and domains", None), ("11. Dates", "Dates"), ("12. Entity identity", "Entity identity & stability")):
        A(""); A(f"## {title}"); A("")
        if sec is None:
            sel = [r for r in res_csv if r["section"] in ("Keys & nulls", "Domains")]
        else:
            sel = [r for r in res_csv if r["section"] == sec]
        A(md_table(["Check", "Status", "Detail"], [(r["check"], r["status"], r["detail"]) for r in sel]))
    A(""); A("Cross-tab TEST_STATUS x COMPLIANCE_STATUS (rows):"); A("")
    A(md_table(["TEST_STATUS"] + COMPLIANCE_STATUSES, [[k] + [v[c] for c in COMPLIANCE_STATUSES] for k, v in P["test_status_by_compliance_status"].items()]))
    A(""); A("## 13. Duplicate and candidate-key analysis"); A("")
    A(md_table(["Key", "Duplicate rows"], list(P["duplicates"].items())))
    A(""); A("Row grain: one row = (EON_ID, METRIC_ID, REPORTING_MONTHEND_DATE). METRIC_ID repeats by design (grouping pattern: Zipf-weighted primary metric per app, same-family secondary metrics - see assumptions B03).")
    A(""); A("## 14. Scenario coverage and longitudinal change"); A("")
    A(md_table(["Scenario", "Entities", "Rows", "Non_Compliant", "Compliant", "Test_Complete", "Test_Pending", "Exempt", "No_Test", "Fail share (completed)", "NC before/after switch"],
               [(k, v["entities"], v["rows"], f"{v['non_compliant_share']:.1%}", f"{v['compliant_share']:.1%}", f"{v['test_complete_share']:.1%}", f"{v['test_pending_share']:.1%}", f"{v['exempt_share']:.1%}", f"{v['no_test_share']:.1%}",
                 "" if v["fail_share_of_completed"] is None else f"{v['fail_share_of_completed']:.1%}",
                 f"{v['nc_share_before_switch']:.1%} -> {v['nc_share_after_switch']:.1%}" if "nc_share_before_switch" in v else "") for k, v in P["scenarios"].items()]))
    tr = P["transitions"]
    A(""); A(f"Month-to-month transitions over {tr['consecutive_month_pairs']:,} consecutive observed application-month pairs: **{tr['new_non_compliance']:,} new non-compliance**, **{tr['resolved_non_compliance']:,} resolved**, {tr['persistent_non_compliance']:,} persistent. ({tr['definition']})")
    A(""); A("Risk code vs compliance (no artificial coupling expected):"); A("")
    A(md_table(["ASSET_RISK_RATING_2", "Rows", "Non_Compliant share", "Fail share of completed tests"],
               [(k, v["rows"], f"{v['non_compliant_share']:.1%}", "" if v["fail_share_of_completed"] is None else f"{v['fail_share_of_completed']:.1%}") for k, v in P["risk_vs_compliance"].items()]))
    A(""); A("Longitudinal checks:"); A("")
    A(md_table(["Check", "Status", "Detail"], [(r["check"], r["status"], r["detail"]) for r in res_csv if r["section"] in ("Grain & duplicates", "Longitudinal behaviour", "Scenarios")]))
    sc = P["disclosure_scan"]
    A(""); A("## 15. Privacy / disclosure scan"); A("")
    A(md_table(["Item", "Result"], [("Status", sc["status"]), ("Findings", sc["n_findings"]), ("String columns scanned", sc["columns_scanned"]),
                                    ("Distinct string values scanned", f"{sc['distinct_values_scanned']:,}"), ("Findings by check", sc["by_check"] or "none"),
                                    ("Scanner self-test (planted violations detected)", next((r["status"] for r in res_csv if "self-test" in r["check"]), ""))]))
    A(""); A("The scan applies to cell values only (column names keep the client's legacy spelling by instruction). The embedded deny-lists are not exhaustive; extend `validation.extra_forbidden_terms`.")
    A(""); A("## 16. Saved-file integrity (CSV vs XLSX vs in-memory)"); A("")
    A(md_table(["Check", "Status", "Detail"], [(r["check"], r["status"], r["detail"]) for r in ex_rows]))
    A(""); A(f"Full validation was also repeated on the re-loaded XLSX `Data` sheet: {c2['PASS']} PASS / {c2['WARN']} WARN / {c2['FAIL']} FAIL "
        f"({'identical outcome to the CSV run' if [r['status'] for r in res_csv] == [r['status'] for r in res_xlsx] else 'DIFFERS from the CSV run - see below'}).")
    diff = [(a["check"], a["status"], b["status"]) for a, b in zip(res_csv, res_xlsx) if a["status"] != b["status"]]
    if diff:
        A(""); A(md_table(["Check", "CSV", "XLSX"], diff))
    A(""); A("## 17. Failed and warning-level checks"); A("")
    bad = [("CSV", r) for r in res_csv if r["status"] != "PASS"] + [("XLSX", r) for r in res_xlsx if r["status"] != "PASS"] + [("Files", r) for r in ex_rows if r["status"] != "PASS"]
    if bad:
        A(md_table(["Source", "Level", "Check", "Detail"], [(s, r["status"], r["check"], r["detail"]) for s, r in bad]))
    else:
        A("None - every check passed.")
    A(""); A("## 18. Candidate golden questions"); A("")
    A(md_table(["ID", "Question", "Status", "SQL == pandas"], [(q["id"], q["question"], q["status"], "yes" if q["verified_sql_vs_pandas"] else "NO") for q in golden]))
    A(""); A("Full SQL and expected results: `golden_questions.md`.")
    A(""); A("## 19. Limitations"); A("")
    for s in ("All distributions are generator assumptions; nothing here is statistically equivalent to the confidential client data.",
              "Numerator/denominator, RFB/TOTAL_RFB, SYSTEM_RTC, tier direction and risk-code direction are provisional (assumptions register C03-C05, D01-D03).",
              "Reporting population grows over the window (about 600 applications in the first month, about 900-960 in the last) because applications enter the window at different months; use rates/shares rather than absolute counts when demonstrating monthly trends (assumptions B05, G06).",
              "The aggregate provisional compliance rate is roughly flat (deteriorating and improving applications offset each other); month-to-month change is concentrated at application / organisation level (new and resolved non-compliance).",
              "The disclosure scan uses embedded, non-exhaustive deny-lists.",
              "The Word prompt's Part 3 line on owner name pairs is truncated in the source; the dictionary rule was used instead (A02)."):
        A(f"- {s}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return overall


# ======================================================================================
# 13. save_outputs + pipeline
# ======================================================================================
def generate_dataset(cfg):
    L = build_lookup_tables(cfg)
    ents, plan = generate_entities(cfg, L)
    df = generate_rows(cfg, L, ents, plan)
    df, repairs = enforce_rules(df, cfg, L)
    return df, L, ents, repairs


def save_outputs(df, cfg, L, ents, out_dir, stage, **kw):
    """stage='data': CSV + metadata lookups.  stage='xlsx': workbook.  Returns file paths."""
    os.makedirs(out_dir, exist_ok=True)
    F = cfg["files"]
    if stage == "data":
        canon = to_canonical(df)
        p = os.path.join(out_dir, F["csv"])
        canon.to_csv(p, index=False, encoding="utf-8", na_rep="", lineterminator="\n")
        write_metadata(cfg, L, ents, os.path.join(out_dir, F["metadata_dir"]))
        assert os.path.getsize(p) > 0
        return p
    if stage == "xlsx":
        p = os.path.join(out_dir, F["xlsx"])
        write_xlsx(p, df, kw["dd_df"], kw["blocks"], kw["assumptions_df"])
        assert os.path.getsize(p) > 0
        return p
    raise ValueError(stage)


def _load_validate(path, kind, cfg, L, ents, dictionary):
    canon = load_csv_canonical(path) if kind == "csv" else load_xlsx_canonical(path)
    typed, issues = coerce_types(canon)
    rows, P = validate_data(typed, cfg, L, ents, source=kind, raw=canon, parse_issues=issues, dictionary=dictionary)
    if P is None:
        bad = "; ".join(f"{r['check']}: {r['detail']}" for r in rows if r["status"] == "FAIL")
        raise RuntimeError(f"schema validation of saved {kind.upper()} failed - {bad}")
    return canon, typed, rows, P


def run_pipeline(cfg: dict) -> int:
    t0 = time.time()
    out_dir = cfg["output_dir"]
    F = cfg["files"]
    print(f"[1/8] generating (seed={cfg['seed']}, rows={cfg['row_count']:,}) ...")
    df, L, ents, repairs = generate_dataset(cfg)
    dictionary = load_source_dictionary(cfg)
    if dictionary is None:
        print("      WARNING: Data_Dictionary_1.xlsx not found; source wording will be missing from the workbook")

    print("[2/8] writing CSV + metadata lookups ...")
    csv_path = save_outputs(df, cfg, L, ents, out_dir, "data")
    csv_sha = file_sha256(csv_path)

    print("[3/8] re-loading CSV and validating the saved file ...")
    canon_csv, typed_csv, res_csv, P = _load_validate(csv_path, "csv", cfg, L, ents, dictionary)
    mem_canon = to_canonical(df)
    file_checks = Results()
    S = "File integrity"
    with open(csv_path, "rb") as fh:
        head = fh.read(4)
        fh.seek(0)
        raw_bytes = fh.read()
    try:
        raw_bytes.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        utf8 = False
    file_checks.add("CSV is valid UTF-8 without BOM", utf8 and head[:3] != b"\xef\xbb\xbf", "", section=S)
    file_checks.add("CSV header row equals the 57 specified column names", raw_bytes.split(b"\n", 1)[0].decode("utf-8").split(",") == EXPECTED_COLUMNS, "", section=S)
    file_checks.add("Saved CSV equals the in-memory frame cell-by-cell", bool(canon_csv.fillna("<N>").equals(mem_canon.fillna("<N>"))), "", section=S)

    print("[4/8] building golden questions + workbook sheets ...")
    golden = build_golden_questions(typed_csv)
    dd_df = build_dd_frame(dictionary, P)
    assumptions_df = pd.DataFrame(ASSUMPTIONS, columns=["ID", "Area", "Decision / assumption", "Status", "Config key"])
    extras = {"csv_sha256": csv_sha}
    blocks = build_summary_blocks(cfg, typed_csv, P, res_csv, extras)

    print("[5/8] writing XLSX (pass 1) and validating the saved workbook ...")
    xlsx_path = save_outputs(typed_csv, cfg, L, ents, out_dir, "xlsx", dd_df=dd_df, blocks=blocks, assumptions_df=assumptions_df)
    canon_x, typed_x, res_x, P_x = _load_validate(xlsx_path, "xlsx", cfg, L, ents, dictionary)
    file_checks.add("XLSX Data sheet equals CSV cell-by-cell", bool(canon_x.fillna("<N>").equals(canon_csv.fillna("<N>"))), "", section=S)

    print("[6/8] determinism check (second full generation) ...")
    df2, _, _, _ = generate_dataset(cfg)
    det = bool(to_canonical(df2).fillna("<N>").equals(mem_canon.fillna("<N>")))
    file_checks.add("Same configuration + seed regenerates an identical dataset", det, "", section=S)

    # second workbook pass: include XLSX + file-integrity results in the Validation Summary sheet
    import openpyxl
    all_for_sheet = res_csv + [dict(r, check="[XLSX reload] " + r["check"]) for r in res_x if r["status"] != "PASS"] + file_checks.rows
    blocks = build_summary_blocks(cfg, typed_csv, P, all_for_sheet, extras)
    save_outputs(typed_csv, cfg, L, ents, out_dir, "xlsx", dd_df=dd_df, blocks=blocks, assumptions_df=assumptions_df)
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    sheets = wb.sheetnames
    dd_rows = pd.read_excel(xlsx_path, sheet_name="Data Dictionary", engine="openpyxl").shape[0]
    wb.close()
    canon_x2 = load_xlsx_canonical(xlsx_path)
    file_checks.add("Workbook has the four required worksheets in order", sheets == ["Data", "Data Dictionary", "Validation Summary", "Assumptions"], str(sheets), section=S)
    file_checks.add("Data Dictionary sheet lists all 57 columns", dd_rows == CONTRACT_COLS, str(dd_rows), section=S)
    file_checks.add("Final XLSX (after summary rewrite) still equals CSV cell-by-cell", bool(canon_x2.fillna("<N>").equals(canon_csv.fillna("<N>"))), "", section=S)

    print("[7/8] writing reports ...")
    extras.update({"checks": file_checks.rows, "deterministic": "yes" if det else "NO", "seconds": round(time.time() - t0, 1)})
    write_assumptions(cfg, os.path.join(out_dir, F["assumptions"]), P)
    write_golden_md(os.path.join(out_dir, F["golden_questions"]), golden, cfg, csv_sha)
    overall = write_validation_report(os.path.join(out_dir, F["validation_report"]), cfg, P, res_csv, res_x, extras, repairs, dictionary, golden)
    profile = {"generator_version": GENERATOR_VERSION, "seed": cfg["seed"], "rows": len(df), "columns": df.shape[1],
               "csv_sha256": csv_sha, "overall_validation": overall, "repairs_applied": repairs,
               "note": "All statistics describe the SYNTHETIC output only; they are not properties of any client source data.",
               "profile": P, "golden_questions": golden,
               "config_digest": hashlib.sha256(json.dumps(to_py(cfg), sort_keys=True).encode()).hexdigest(),
               "validation": {"csv": res_csv, "xlsx_non_pass": [r for r in res_x if r["status"] != "PASS"], "files": file_checks.rows}}
    with open(os.path.join(out_dir, F["profile"]), "w", encoding="utf-8") as fh:
        json.dump(to_py(profile), fh, indent=2)

    n_fail = sum(1 for r in res_csv + res_x + file_checks.rows if r["status"] == "FAIL")
    n_warn = sum(1 for r in res_csv + res_x + file_checks.rows if r["status"] == "WARN")
    print("[8/8] summary")
    er = P["entity_repetition"]
    print(f"      rows={len(df):,} cols={df.shape[1]} distinct EON_ID={er['distinct_eon_id']:,} METRIC_ID={er['distinct_metric_id']} "
          f"periods={df['REPORTING_MONTHEND_DATE'].nunique()} ({df['REPORTING_MONTHEND_DATE'].min():%Y-%m-%d}..{df['REPORTING_MONTHEND_DATE'].max():%Y-%m-%d})")
    print(f"      checks: CSV {sum(r['status']=='PASS' for r in res_csv)} pass | XLSX {sum(r['status']=='PASS' for r in res_x)} pass | files {sum(r['status']=='PASS' for r in file_checks.rows)} pass | WARN={n_warn} FAIL={n_fail}")
    print(f"      disclosure scan: {P['disclosure_scan']['status']} ({P['disclosure_scan']['n_findings']} findings) | deterministic: {det} | golden questions verified: {sum(q['verified_sql_vs_pandas'] for q in golden)}/{len(golden)}")
    for s, rs in (("CSV", res_csv), ("XLSX", res_x), ("FILES", file_checks.rows)):
        for r in rs:
            if r["status"] != "PASS":
                print(f"      [{s}] {r['status']}: {r['check']} -> {r['detail']}")
    print(f"      outputs in: {os.path.abspath(out_dir)}  ({time.time() - t0:.1f}s)")
    return 1 if (n_fail or not all(q["verified_sql_vs_pandas"] for q in golden)) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the privacy-safe synthetic enterprise dataset (offline, deterministic).")
    ap.add_argument("--seed", type=int, help=f"random seed (default {CONTRACT_SEED})")
    ap.add_argument("--rows", type=int, help=f"data rows (default {CONTRACT_ROWS})")
    ap.add_argument("--output-dir", help="output directory (default client_dataset_output)")
    ap.add_argument("--config", help="JSON file deep-merged over PROFILE_CONFIG")
    a = ap.parse_args(argv)
    ov: dict = {}
    if a.seed is not None:
        ov["seed"] = a.seed
    if a.rows is not None:
        ov["row_count"] = a.rows
    if a.output_dir:
        ov["output_dir"] = a.output_dir
    cfg = build_config(ov, a.config)
    return run_pipeline(cfg)


if __name__ == "__main__":
    sys.exit(main())
