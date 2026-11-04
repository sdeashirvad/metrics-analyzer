"""Prepared investigation bundles. These tests do not open Snowflake."""

from __future__ import annotations

import json
from pathlib import Path

from app.portfolio.definitions import DEFINITIONS_VERSION
from app.portfolio.prepared import (
    bundle_is_current,
    can_publish,
    match_metric_bundle,
    publish_bundle,
    reconcile_context,
    select_priority,
    source_fact_validation,
)
from app.portfolio.scope import Scope
from app.common.v2_envelope import DATASET_VERSION
from app.agents.prepare_investigations import consider


def _metric(metric_id, non_compliant, rag, failed, persistent):
    return {
        "metricId": metric_id,
        "nonCompliant": non_compliant,
        "rag": rag,
        "failedTests": failed,
        "persistent": persistent,
        "applications": non_compliant + 2,
        "numerator": non_compliant,
        "denominator": 10,
        "rate": non_compliant / 10,
    }


def _document(metric_id="M000001", month="2026-10-31", text="12 non-compliant of 20 applications. Numerator 12 and denominator 20. Rate 60."):
    return {
        "metricId": metric_id,
        "scopeType": "metric",
        "reportingDate": month,
        "scope": {"orgTree": "BUSINESS_ORG", "l1": [], "l2": [], "legalEntity": [], "tier": [], "risk": [], "lifecycle": [], "ma": None},
        "datasetVersion": DATASET_VERSION,
        "definitionsVersion": DEFINITIONS_VERSION,
        "agent": "METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1",
        "generatedAt": "2026-11-04T00:00:00Z",
        "threadId": 7,
        "conversationId": "handle",
        "runId": "run",
        "messageId": "9",
        "context_reconciliation": "PASS",
        "band_consistency": "PASS",
        "source_fact_validation": "PARTIAL",
        "source_fact_limitation": "Other figures were not tied to a source query.",
        "agent_response_status": "COMPLETED",
        "content": {"kind": "analysis", "text": text, "evidence": [], "toolActivity": [], "suggestedFollowUps": [], "notices": [], "warnings": []},
    }


def test_priority_order_is_deterministic():
    chosen = select_priority([
        _metric("M000003", 4, "amber", 9, 9),
        _metric("M000001", 10, "red", 1, 1),
        _metric("M000002", 10, "red", 3, 0),
        _metric("M000004", 10, "amber", 8, 8),
    ], limit=3)
    assert [item["metricId"] for item in chosen] == ["M000002", "M000001", "M000004"]


def test_context_reconciliation_is_separate_from_the_prose():
    expected = {"nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6}
    assert reconcile_context(expected, expected) == "PASS"
    assert reconcile_context(expected, {**expected, "nonCompliant": 11}) == "FAIL"


def test_source_facts_do_not_claim_complete_validation_for_extra_figures():
    status, note = source_fact_validation(
        "12 non-compliant of 20. Numerator 12 denominator 20. The rate is 60. Division 44 also moved.",
        {"nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6},
    )
    assert status == "PARTIAL"
    assert note and "44" in note
    clean, limitation = source_fact_validation(
        "12 non-compliant of 20. Numerator 12 denominator 20. The rate is 60.",
        {"nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6},
    )
    assert clean == "PASS"
    assert limitation is None


def test_contradiction_fails_source_validation():
    status, note = source_fact_validation("There are 4 non-compliant applications.", {"nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6})
    assert status == "FAIL"
    assert note


def test_incomplete_generation_is_not_published(tmp_path: Path):
    valid = _document()
    publish_bundle(valid, tmp_path)
    invalid = _document()
    invalid["agent_response_status"] = "FAILED"
    invalid["content"] = {"kind": "analysis", "text": ""}
    assert can_publish(invalid) is False
    try:
        publish_bundle(invalid, tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid bundle was published")
    kept = json.loads((tmp_path / "M000001.json").read_text(encoding="utf-8"))
    assert kept["content"]["text"].startswith("12 non-compliant")


def test_mismatch_rejects_the_bundle(tmp_path: Path):
    publish_bundle(_document(month="2026-10-31"), tmp_path)
    assert match_metric_bundle("M000001", "2026-09-30", Scope(), DATASET_VERSION, DEFINITIONS_VERSION, tmp_path) is None
    changed = _document()
    changed["datasetVersion"] = "other"
    publish_bundle(changed, tmp_path)
    assert match_metric_bundle("M000001", "2026-10-31", Scope(), DATASET_VERSION, DEFINITIONS_VERSION, tmp_path) is None
    publish_bundle(_document(), tmp_path)
    assert match_metric_bundle("M000001", "2026-10-31", Scope(l1=("Retail",)), DATASET_VERSION, DEFINITIONS_VERSION, tmp_path) is None
    assert match_metric_bundle("M000001", "2026-10-31", Scope(), DATASET_VERSION, DEFINITIONS_VERSION, tmp_path)["metricId"] == "M000001"


def test_context_rate_ignores_the_sentence_period():
    from app.agents.prepare_investigations import _context_facts

    rendered = "Numerator 26, denominator 46, provisional rate 0.565217. Non-compliant metric rows: 20. Metric rows in scope: 64."
    facts = _context_facts(rendered, {"rate": 0.565217})
    assert facts["numerator"] == 26
    assert facts["denominator"] == 46
    assert facts["rate"] == 0.565217
    assert facts["nonCompliant"] == 20
    assert facts["applications"] == 64


def test_failed_generation_does_not_replace_a_valid_bundle(tmp_path: Path):
    from app.portfolio import prepared

    original = prepared.BUNDLE_DIR
    prepared.BUNDLE_DIR = tmp_path
    try:
        publish_bundle(_document(), tmp_path)
        metric = _metric("M000001", 12, "red", 1, 1)
        row = consider(metric, _document(), None, force=True, month="2026-10-31")
        assert row["status"] == "failed"
        assert bundle_is_current(json.loads((tmp_path / "M000001.json").read_text(encoding="utf-8")), month="2026-10-31", dataset_version=DATASET_VERSION, definitions_version=DEFINITIONS_VERSION)
    finally:
        prepared.BUNDLE_DIR = original


def test_band_consistency_rejects_a_narrative_that_contradicts_the_band():
    from app.portfolio.prepared import band_consistency

    assert band_consistency("The rate is 44.5%, inside the green band. Nothing here needs attention.", "green")[0] == "FAIL"
    assert band_consistency("The rate is 44.5% and sits in the healthy band. Review contributors.", "green")[0] == "PASS"
    assert band_consistency("This metric is healthy.", "red")[0] == "FAIL"
    assert band_consistency("This metric is not healthy at 84.6%.", "red")[0] == "PASS"
    assert band_consistency("A higher rate is better here.", "amber")[0] == "FAIL"


def test_band_inconsistent_analysis_is_not_published(tmp_path: Path):
    from app.agents.prepare_investigations import assemble

    metric = {"metricId": "M000001", "nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6, "rag": "green"}
    produced = {
        "content": {"kind": "analysis", "text": "12 non-compliant of 20. Numerator 12 denominator 20. Rate 60. This needs attention."},
        "facts": {"nonCompliant": 12, "applications": 20, "numerator": 12, "denominator": 20, "rate": 0.6},
        "generatedAt": "2026-11-04T00:00:00Z",
        "agent_response_status": "COMPLETED",
    }
    document = assemble(metric, produced, month="2026-10-31")
    assert document["band_consistency"] == "FAIL"
    assert can_publish(document) is False


def test_context_carries_band_and_direction():
    from app.agents.context.builder import _band_line

    line = _band_line(0.445, "green")
    assert "Green (healthy)" in line and "higher rate is worse" in line and "45%" in line
    assert _band_line(None, "green") is None
