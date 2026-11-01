import pytest

from app.analysis.validator import ValidationError, assert_supported, parse_narrative
from app.dq.mapping import desk_names_in, discrepancy_sentence


def test_summary_json_and_supported_numbers():
    facts = {
        "controlId": "DQ-020",
        "snapshot": {"passRate": 98.178, "failed": 3161, "total": 173463, "asOf": "2026-10-28", "rag": "red"},
    }
    narrative = parse_narrative(
        '{"text":"Pass rate is 98.178.","movement":"Still red.","thresholdPosition":"Below the line.","implications":"3161 failed of 173463."}',
        "SUMMARY",
    )
    assert_supported(narrative, facts, "DQ-020")


def test_rejects_a_different_control_and_invalid_json():
    facts = {"controlId": "DQ-020", "snapshot": {"failed": 3161}}
    narrative = parse_narrative(
        '{"text":"See DQ-007.","movement":"n/a","thresholdPosition":"n/a","implications":"n/a"}',
        "SUMMARY",
    )
    with pytest.raises(ValidationError):
        assert_supported(narrative, facts, "DQ-020")
    with pytest.raises(ValidationError):
        parse_narrative("not json", "SUMMARY")


def test_rejects_a_contradictory_rag_and_an_invented_open_count():
    facts = {
        "controlId": "DQ-020",
        "snapshot": {"rag": "red", "openExceptions": 130, "passRate": 98.178, "failed": 3161},
        "thresholds": {"green": 99.5, "amber": 98.0},
    }
    contradictory = parse_narrative(
        '{"text":"The status is green.","movement":"Improved.","thresholdPosition":"Above the line.","implications":"None."}',
        "SUMMARY",
    )
    invented = parse_narrative(
        '{"text":"There are 50 open exceptions.","movement":"Still red.","thresholdPosition":"Below the line.","implications":"Open work remains."}',
        "SUMMARY",
    )
    with pytest.raises(ValidationError):
        assert_supported(contradictory, facts, "DQ-020")
    with pytest.raises(ValidationError):
        assert_supported(invented, facts, "DQ-020")


def test_accepts_a_narrative_that_uses_snapshot_facts():
    facts = {
        "controlId": "DQ-020",
        "snapshot": {"rag": "red", "openExceptions": 130, "passRate": 98.178, "failed": 3161, "total": 173463},
        "thresholds": {"green": 99.5, "amber": 98.0},
    }
    narrative = parse_narrative(
        '{"text":"The green threshold is 99.5 and the status is red. 130 open exceptions remain.","movement":"Still red.","thresholdPosition":"Pass rate is 98.178.","implications":"3161 failed records of 173463 total records."}',
        "SUMMARY",
    )
    assert_supported(narrative, facts, "DQ-020")


def test_accepts_the_rounded_share_of_two_supplied_desk_failures():
    facts = {
        "controlId": "DQ-020",
        "snapshot": {"rag": "red", "failed": 3161, "total": 173463, "passRate": 98.178, "asOf": "2026-10-28"},
        "desks": [
            {"deskName": "Commodities", "failed": 2361, "total": 12788, "passRate": 81.537},
            {"deskName": "Securitised Products", "failed": 397, "total": 7075, "passRate": 94.389},
        ],
    }
    narrative = parse_narrative(
        '{"hypothesis":["The supplied desk rows concentrate the failures."],'
        '"validationSteps":["Compare the supplied desk failed counts with 3161."],'
        '"implications":"Commodities and Securitised Products account for 87.3% of the 3161 failures. The status is red."}',
        "INVESTIGATION",
    )
    assert_supported(narrative, facts, "DQ-020")
    invented = parse_narrative(
        '{"hypothesis":["The supplied desk rows concentrate the failures."],'
        '"validationSteps":["Compare the supplied desk failed counts with 3161."],'
        '"implications":"Those desks account for 12.5% of failures. The status is red."}',
        "INVESTIGATION",
    )
    with pytest.raises(ValidationError):
        assert_supported(invented, facts, "DQ-020")


def test_discrepancy_uses_desk_names_without_a_fixed_control():
    names = ["Commodities", "Securitised Products", "Treasury & Funding"]
    story = desk_names_in("Commodities and Securitised are the hotspots", names)
    commentary = desk_names_in("The break is on Treasury & Funding", names)
    sentence = discrepancy_sentence("DQ-020", story, commentary)
    assert sentence is not None
    assert "Commodities" in sentence
    assert "Treasury & Funding" in sentence
    assert discrepancy_sentence("DQ-001", {"Commodities"}, {"Commodities"}) is None
