"""Reject narrative that cites a control, date, or number the query did not return."""

from __future__ import annotations

import json
import re
from decimal import Decimal

_CONTROL = re.compile(r"\bDQ-\d{3}\b")
_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_NUMBER = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d+\b|\b\d{4,}\b")
# Current-status claims only. Threshold names such as "green threshold" are not claims.
_RAG_CLAIM = re.compile(
    r"\b(?:current\s+)?(?:rag(?:\s+status)?|status)\s+(?:is|remains|stays|=|:)\s*(green|amber|red)\b"
    r"|\b(?:currently|remains|still|stays)\s+(green|amber|red)\b"
    r"|\bcontrol\s+is\s+(green|amber|red)\b",
    re.IGNORECASE,
)
# Counts tied to a measured label. Bare small numbers in ordinary prose are left alone.
_COUNT_CLAIM = re.compile(
    r"\b(\d[\d,]*)\s+open\s+exceptions?\b"
    r"|\bopen\s+exceptions?\s*(?:is|are|of|:)?\s*(\d[\d,]*)\b"
    r"|\b(\d[\d,]*)\s+failed\s+records?\b"
    r"|\bfailed\s+records?\s*(?:is|are|of|:)?\s*(\d[\d,]*)\b"
    r"|\b(\d[\d,]*)\s+total\s+records?\b"
    r"|\btotal\s+records?\s*(?:is|are|of|:)?\s*(\d[\d,]*)\b"
    r"|\b(\d[\d,]*)\s+exceptions?\b"
    r"|\bexception\s+count\s*(?:is|are|of|:)?\s*(\d[\d,]*)\b",
    re.IGNORECASE,
)


class ValidationError(Exception):
    pass


def parse_narrative(text: str, analysis_type: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValidationError("Agent text was not JSON")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValidationError("Agent text was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Agent JSON was not an object")
    if analysis_type == "SUMMARY":
        for key in ("text", "movement", "thresholdPosition", "implications"):
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                raise ValidationError(f"Summary is missing {key}")
        return {key: payload[key].strip() for key in ("text", "movement", "thresholdPosition", "implications")}
    if analysis_type == "INVESTIGATION":
        hypothesis = payload.get("hypothesis")
        steps = payload.get("validationSteps")
        implications = payload.get("implications")
        if not isinstance(hypothesis, list) or not hypothesis or not all(isinstance(item, str) and item.strip() for item in hypothesis):
            raise ValidationError("Investigation hypothesis must be a non-empty list of strings")
        if not isinstance(steps, list) or not all(isinstance(item, str) and item.strip() for item in steps):
            raise ValidationError("Investigation validationSteps must be a list of strings")
        if not isinstance(implications, str) or not implications.strip():
            raise ValidationError("Investigation is missing implications")
        return {
            "hypothesis": [item.strip() for item in hypothesis],
            "validationSteps": [item.strip() for item in steps],
            "implications": implications.strip(),
        }
    raise ValidationError("Unknown analysis type")


def assert_supported(narrative: dict, facts: dict, control_id: str) -> None:
    blob = json.dumps(narrative)
    allowed_text, allowed_numbers, allowed_dates = _allow(facts, control_id)
    for cited in _CONTROL.findall(blob):
        if cited != control_id:
            raise ValidationError("Narrative cites a control that was not retrieved")
    for cited in _DATE.findall(blob):
        if cited not in allowed_dates:
            raise ValidationError("Narrative cites a date that was not retrieved")
    for token in _NUMBER.findall(blob):
        if not _number_allowed(token, allowed_numbers, allowed_text):
            raise ValidationError("Narrative cites a value that was not retrieved")
    _assert_rag(blob, facts)
    _assert_labeled_counts(blob, allowed_numbers, allowed_text)


def _allow(facts: dict, control_id: str) -> tuple[str, set[str], set[str]]:
    text_parts: list[str] = []
    numbers: set[str] = set()
    dates: set[str] = set()

    def walk(value) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float, Decimal)):
            _add_number(numbers, value)
            text_parts.append(str(value))
            return
        text = str(value)
        text_parts.append(text)
        if _DATE.fullmatch(text):
            dates.add(text)
        for token in _NUMBER.findall(text):
            numbers.add(token.replace(",", ""))

    walk(facts)
    text_parts.append(control_id)
    return "\n".join(text_parts), numbers, dates


def _add_number(numbers: set[str], value) -> None:
    number = float(value)
    if number.is_integer():
        as_int = str(int(number))
        numbers.add(as_int)
        numbers.add(f"{int(number):,}")
    numbers.add(str(number))
    numbers.add(f"{number:.1f}")
    numbers.add(f"{number:.2f}")
    numbers.add(f"{number:.3f}")
    numbers.add(f"{number:.4f}")


def _assert_rag(blob: str, facts: dict) -> None:
    claims = {match.group(match.lastindex).lower() for match in _RAG_CLAIM.finditer(blob)}
    if not claims:
        return
    authoritative = _snapshot_rag(facts)
    if authoritative is None or any(claim != authoritative for claim in claims):
        raise ValidationError("Narrative states a RAG that does not match the snapshot")


def _snapshot_rag(facts: dict) -> str | None:
    snapshot = facts.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    rag = snapshot.get("rag")
    if isinstance(rag, str) and rag.strip().lower() in {"green", "amber", "red"}:
        return rag.strip().lower()
    return None


def _assert_labeled_counts(blob: str, allowed_numbers: set[str], allowed_text: str) -> None:
    for match in _COUNT_CLAIM.finditer(blob):
        token = next(group for group in match.groups() if group)
        if not _number_allowed(token, allowed_numbers, allowed_text):
            raise ValidationError("Narrative cites a count that was not retrieved")


def _number_allowed(token: str, allowed_numbers: set[str], allowed_text: str) -> bool:
    plain = token.replace(",", "")
    if token in allowed_numbers or plain in allowed_numbers:
        return True
    try:
        value = float(plain)
    except ValueError:
        return False
    for candidate in allowed_numbers:
        try:
            if abs(float(candidate) - value) < 0.001:
                return True
        except ValueError:
            continue
    return plain in allowed_text
