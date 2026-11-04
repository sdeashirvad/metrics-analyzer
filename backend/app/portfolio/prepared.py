"""Prepared metric investigations stored as JSON files.

Selection uses the latest month and the default business-organisation scope.
A file is served only when metric, month, scope, dataset version, and
definitions version all match, and only after a completed agent response was
parsed and its context reconciled.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.portfolio.definitions import RAG_RANK

BUNDLE_DIR = Path(__file__).resolve().parents[1] / "fallback_assets" / "v2" / "investigations"
REPORT_NAME = "generation_report.json"
PRIORITY_LIMIT = 6

_INT = re.compile(r"(?<![\d.])(\d{1,6})(?:\.0+)?(?!\d)")
_NEAR_NON_COMPLIANT = re.compile(
    r"(\d{1,6})\s+non[-\s]?compliant|non[-\s]?compliant(?:\s+\w+){0,3}\s+(\d{1,6})",
    re.IGNORECASE,
)


def select_priority(metrics: list[dict], limit: int = PRIORITY_LIMIT) -> list[dict]:
    """Rank metrics for prepared analysis.

    Order, all descending, with metric id ascending as the last tie-break:
    non-compliant application count, provisional RAG severity, failed-test
    rows, then persistent non-compliance. Metrics without an id are ignored.
    """

    usable = [item for item in metrics if isinstance(item.get("metricId"), str) and item["metricId"]]

    def key(item: dict):
        return (
            -_count(item.get("nonCompliant")),
            -RAG_RANK.get(str(item.get("rag") or "unclassified"), 0),
            -_count(item.get("failedTests")),
            -_count(item.get("persistent")),
            str(item["metricId"]),
        )

    ordered = sorted(usable, key=key)
    return ordered[:limit]


def reconcile_context(expected: dict, stored: dict) -> str:
    """PASS when the stored context repeats the portfolio figures. This does not check the prose."""

    keys = ("nonCompliant", "applications", "numerator", "denominator")
    for name in keys:
        if _count(expected.get(name)) != _count(stored.get(name)):
            return "FAIL"
    if _rate(expected.get("rate")) != _rate(stored.get("rate")):
        return "FAIL"
    return "PASS"


def source_fact_validation(text: str, facts: dict) -> tuple[str, str | None]:
    """Check figures that can be tied to a source query.

    PASS means every supplied figure appears and no nearby non-compliant count
    contradicts the source. PARTIAL means the explanation could not be checked
    in full. FAIL means the prose states a different non-compliant count, or
    there is no prose to check.
    """

    prose = text.strip()
    if not prose:
        return "FAIL", "The agent response has no prose to check."
    labelled = [int(number) for match in _NEAR_NON_COMPLIANT.findall(prose) for number in match if number]
    non_compliant = facts.get("nonCompliant")
    if labelled and non_compliant is not None and all(value != _count(non_compliant) for value in labelled):
        return "FAIL", "The explanation states a non-compliant count that does not match the source query."
    known = _fact_numbers(facts)
    missing = [name for name, value in known.items() if not _number_present(prose, value)]
    if missing:
        listed = ", ".join(missing)
        return "PARTIAL", f"These source figures were not found in the explanation: {listed}."
    allowed = set(known.values())
    extra = []
    for token in _INT.findall(prose):
        number = int(token)
        if number in allowed or 1900 <= number <= 2100:
            continue
        extra.append(number)
    if extra:
        shown = ", ".join(str(number) for number in extra[:8])
        return "PARTIAL", f"The supplied source figures appear. These other figures were not tied to a source query: {shown}."
    return "PASS", None


_BAND_CONTRADICTIONS = {
    "green": [
        r"needs?\s+(?:urgent\s+)?attention",
        r"requires?\s+(?:urgent\s+)?attention",
        r"above\s+the\s+(?:provisional\s+)?green",
        r"outside\s+the\s+(?:provisional\s+)?green",
        r"\bunhealthy\b",
        r"\bin\s+the\s+red\b",
        r"\bred\s+band\b",
    ],
    "amber": [
        r"needs?\s+(?:urgent\s+)?attention",
        r"\bred\s+band\b",
        r"\bin\s+the\s+red\b",
        r"\bunhealthy\b",
    ],
    "red": [
        r"(?<!not\s)(?<!un)\bhealthy\b",
        r"\bwithin\s+the\s+(?:provisional\s+)?green",
        r"\bin\s+the\s+green\s+band\b",
    ],
}
_DIRECTION_CONTRADICTIONS = [
    r"higher\s+(?:provisional\s+)?rates?\s+(?:is|are|means?)\s+(?:better|good)",
    r"lower\s+(?:provisional\s+)?rates?\s+(?:is|are|means?)\s+(?:worse|bad)",
]


def band_consistency(text: str, rag: str | None) -> tuple[str, str | None]:
    """PASS when the prose does not contradict the central band or its direction.

    The band comes from `classify_rate`. This is a narrow phrase check, not a reading of the prose.
    """

    prose = " ".join(text.split())
    for pattern in _DIRECTION_CONTRADICTIONS:
        if re.search(pattern, prose, re.IGNORECASE):
            return "FAIL", "The explanation reverses the direction of the provisional band."
    for pattern in _BAND_CONTRADICTIONS.get(str(rag), []):
        if re.search(pattern, prose, re.IGNORECASE):
            return "FAIL", f"The explanation contradicts the {rag} provisional band."
    return "PASS", None


def can_publish(document: dict) -> bool:
    content = document.get("content")
    text = content.get("text") if isinstance(content, dict) else None
    return (
        document.get("agent_response_status") == "COMPLETED"
        and document.get("context_reconciliation") == "PASS"
        and document.get("source_fact_validation") != "FAIL"
        and document.get("band_consistency") != "FAIL"
        and isinstance(text, str)
        and bool(text.strip())
        and content.get("kind") == "analysis"
    )


def publish_bundle(document: dict, directory: Path | None = None) -> Path:
    """Write a valid bundle atomically. An invalid document is not published."""

    if not can_publish(document):
        raise ValueError("incomplete analysis is not published")
    folder = directory or BUNDLE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{document['metricId']}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target


def write_report(report: dict, directory: Path | None = None) -> Path:
    folder = directory or BUNDLE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / REPORT_NAME
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target


def bundle_is_current(document: dict, *, month: str, dataset_version: str, definitions_version: str) -> bool:
    return (
        can_publish(document)
        and document.get("band_consistency") == "PASS"
        and document.get("reportingDate") == month
        and document.get("datasetVersion") == dataset_version
        and document.get("definitionsVersion") == definitions_version
        and _scope_is_default(document.get("scope"))
    )


def match_metric_bundle(
    metric_id: str,
    month: str,
    scope,
    dataset_version: str,
    definitions_version: str,
    directory: Path | None = None,
) -> dict | None:
    """Return a prepared bundle only for an exact default-scope match."""

    if not getattr(scope, "unfiltered", lambda: False)():
        return None
    path = (directory or BUNDLE_DIR) / f"{metric_id}.json"
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("metricId") != metric_id or document.get("scopeType") != "metric":
        return None
    if not bundle_is_current(document, month=month, dataset_version=dataset_version, definitions_version=definitions_version):
        return None
    return document


def analysis_ref(run_id: str | None, bundle: dict | None, label: str) -> dict:
    if bundle is None:
        return {
            "status": "NOT_RUN",
            "source": None,
            "precomputed": None,
            "conversationId": None,
            "runId": None,
            "messageId": None,
            "generatedAt": None,
            "stale": False,
            "label": label,
        }
    return {
        "status": "FALLBACK_STATIC",
        "source": "precomputed",
        "precomputed": {
            "source": "precomputed",
            "target": {"kind": "metric", "metricId": bundle["metricId"]},
            "month": bundle["reportingDate"],
            "generatedAt": bundle["generatedAt"],
            "datasetVersion": bundle["datasetVersion"],
            "definitionsVersion": bundle["definitionsVersion"],
            "agentSpecVersion": bundle.get("agent"),
            "stale": False,
            "staleReason": None,
            "label": "Prepared analysis.",
            "content": bundle["content"],
            "sourceFactValidation": bundle.get("source_fact_validation"),
            "sourceFactLimitation": bundle.get("source_fact_limitation"),
            "displayName": bundle.get("displayName"),
            "dataAsOf": bundle.get("dataAsOf") or bundle["reportingDate"],
            "sourceSnapshot": bundle.get("sourceSnapshot"),
            "rag": bundle.get("rag"),
        },
        "conversationId": bundle.get("conversationId"),
        "runId": bundle.get("runId") or run_id,
        "messageId": bundle.get("messageId"),
        "generatedAt": bundle.get("generatedAt"),
        "stale": False,
        "label": label,
    }


def _scope_is_default(scope: object) -> bool:
    if not isinstance(scope, dict):
        return False
    return (
        scope.get("orgTree") == "BUSINESS_ORG"
        and not scope.get("l1")
        and not scope.get("l2")
        and not scope.get("legalEntity")
        and not scope.get("tier")
        and not scope.get("risk")
        and not scope.get("lifecycle")
        and scope.get("ma") in (None, "")
    )


def _fact_numbers(facts: dict) -> dict[str, int]:
    found = {}
    for name in ("nonCompliant", "applications", "numerator", "denominator"):
        value = facts.get(name)
        if value is not None:
            found[name] = _count(value)
    rate = facts.get("rate")
    if isinstance(rate, (int, float)):
        found["ratePercent"] = int(round(float(rate) * 100))
    return found


def _number_present(text: str, value: int) -> bool:
    return str(value) in {match for match in _INT.findall(text)}


def _count(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rate(value: object) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return None
