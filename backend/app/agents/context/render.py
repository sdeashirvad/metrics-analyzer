"""Readable context text, the context hash, and the first-message envelope."""

from __future__ import annotations

import hashlib
import hmac
import json
import re

PREAMBLE = "Context supplied by the application. It is the scope of the question. Do not assume anything not listed."
_REF = re.compile(r"^MA2-REF v1(?:\s+\S+=\S*)+$")


def sanitize(value: object, limit: int = 80) -> str:
    text = "" if value is None else str(value)
    cleaned = "".join(ch for ch in text if ch not in "\r\n\t" and 32 <= ord(ch) != 127)
    cleaned = cleaned.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def clip(text: str, limit: int = 400) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def month_chip(month: str) -> str:
    import calendar

    year, month_number, _day = (int(part) for part in month.split("-"))
    return f"{calendar.month_abbr[month_number]} {year}"


def context_material(
    *,
    definitions_version: str,
    promoted_at: str | None,
    scope: dict,
    item_keys: list[str],
    rendered_text: str,
) -> str:
    body = {"items": sorted(item_keys), "scope": scope}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "\n".join(
        [
            "ma2-context-v1",
            definitions_version,
            promoted_at or "",
            canonical,
            rendered_text,
        ]
    )


def context_hash(**kwargs) -> str:
    return hashlib.sha256(context_material(**kwargs).encode("utf-8")).hexdigest()


def hashes_match(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left.lower().encode("utf-8"), right.lower().encode("utf-8"))


def active_filters_wire(filters: dict) -> dict:
    wire: dict = {}
    if filters.get("orgTree") not in (None, "BUSINESS_ORG"):
        wire["orgTree"] = filters["orgTree"]
    for key in ("l1", "l2", "legalEntity", "tier", "risk", "lifecycle"):
        if filters.get(key):
            wire[key] = filters[key]
    if filters.get("ma"):
        wire["ma"] = filters["ma"]
    return wire


def ma2_ref(
    *,
    agent_key: str,
    client_request_id: str,
    context_hash: str,
    definitions_version: str,
    entry_surface: str,
    month: str,
    month_source: str,
    metric_id: str | None,
    eon_id: str | None,
    created_at: str | None = None,
    retry_of: str | None = None,
) -> str:
    line = (
        f"MA2-REF v1 agent={agent_key} request={client_request_id} "
        f"ctx={context_hash[:12]} definitions={definitions_version or '-'} "
        f"surface={entry_surface} month={month} monthSource={month_source} "
        f"metric={metric_id or '-'} application={eon_id or '-'}"
    )
    if created_at:
        line += f" created={created_at}"
    if retry_of:
        line += f" retry-of={retry_of}"
    return line


def parse_ref(line: str) -> dict[str, str]:
    if not _REF.match(line.strip()):
        return {}
    parsed: dict[str, str] = {}
    for token in line.split()[2:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    return parsed


def compose_first_message(
    *,
    rendered: str,
    entry_surface: str,
    month: str,
    metric_id: str | None,
    eon_id: str | None,
    filters: dict,
    question: str,
    ref: str,
) -> str:
    wire = {
        "entry_surface": "general" if entry_surface in {"general", "dashboard"} else "register_row",
        "eon_id": eon_id,
        "metric_id": metric_id,
        "reporting_monthend_date": month,
        "active_filters": active_filters_wire(filters),
        "user_question": question,
    }
    encoded = json.dumps(wire, ensure_ascii=False, separators=(",", ":"))
    return f"{rendered.rstrip()}\n{encoded}\n{ref}"


def read_user_message(payload: object) -> dict:
    raw = _message_text(payload)
    ref: dict[str, str] = {}
    question = None
    scope = None
    lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("MA2-REF "):
            ref = parse_ref(line) or ref
            continue
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}") and "user_question" in stripped:
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if isinstance(obj, dict) and isinstance(obj.get("user_question"), str):
                question = obj["user_question"]
                scope = obj
                continue
        if stripped and stripped != PREAMBLE:
            lines.append(line)
    if question is None:
        question = "\n".join(lines).strip()
        lines = []
    return {"text": question.strip(), "ref": ref, "lines": lines, "scope": scope}


def chips_from_ref(ref: dict[str, str]) -> list[str]:
    chips = []
    metric = ref.get("metric")
    if metric and metric != "-":
        chips.append(f"Metric {sanitize(metric, 20)}")
    application = ref.get("application")
    if application and application != "-":
        chips.append(f"Application {sanitize(application, 20)}")
    month = ref.get("month")
    if month:
        try:
            label = month_chip(month)
        except (ValueError, IndexError):
            label = month
        if ref.get("monthSource") == "latest_available":
            label = f"{label} (latest available)"
        chips.append(label)
    return chips


def _message_text(payload: object) -> str:
    document = payload
    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError:
            return payload
    if isinstance(document, dict):
        nested = document.get("message_payload")
        if isinstance(nested, str):
            return _message_text(nested)
        content = document.get("content")
        if isinstance(content, list):
            parts = [
                item["text"]
                for item in content
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
            ]
            if parts:
                return "\n".join(parts)
        if isinstance(document.get("text"), str):
            return document["text"]
    return "" if document is None else str(document)
