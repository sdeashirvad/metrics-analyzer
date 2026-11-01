import json

from app.config import INVESTIGATION_PROMPT, SUMMARY_PROMPT


def summary_prompt(facts: dict) -> str:
    return (
        "Return JSON only. Do not use markdown. Keys must be exactly "
        "text, movement, thresholdPosition, and implications. "
        "Each value is a string. Use only the FACTS object. "
        "Copy numbers, dates, control ids, and desk names exactly as they appear in FACTS. "
        "Do not state a pass rate, RAG, failed count, or total that is not in FACTS. "
        "A linked event is not a cause.\n\nFACTS:\n"
        + json.dumps(facts, default=str)
    )


def investigation_prompt(facts: dict) -> str:
    return (
        "Return JSON only. Do not use markdown. Keys must be exactly "
        "hypothesis, implications, and validationSteps. "
        "hypothesis and validationSteps are arrays of strings. implications is a string. "
        "Use only the FACTS object. Copy numbers, dates, control ids, and desk names exactly as they appear in FACTS. "
        "Do not restate a different pass rate, RAG, failed count, or total. "
        "You may compare the planted story, commentary, and events. "
        "A linked event is not a cause.\n\nFACTS:\n"
        + json.dumps(facts, default=str)
    )


def prompt_version(analysis_type: str) -> str:
    if analysis_type == "SUMMARY":
        return SUMMARY_PROMPT
    if analysis_type == "INVESTIGATION":
        return INVESTIGATION_PROMPT
    raise ValueError(analysis_type)
