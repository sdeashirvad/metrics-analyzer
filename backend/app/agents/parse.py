"""Tool-aware parser for one assistant message (contract 6.4)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.registry import ANALYSIS_EVIDENCE_ROWS, MAX_MESSAGE_BYTES, MAX_ROWS

logger = logging.getLogger(__name__)

_AGENT_NOTICE = "Agent-generated. Explanations of cause are hypotheses until validated."
_LIMIT = re.compile(r"LIMIT\s+(\d+)\s*(?:/\*.*?\*/\s*)?;?\s*$", re.IGNORECASE | re.DOTALL)
_HEADING = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[ \t]*(interpreted intent|assumptions|generated sql|result dataset|truncation)(?:\*\*)?[ \t]*:?[ \t]*$"
)


def _user_prose(value: object) -> str | None:
    """Plain assistant prose. Tool payloads and JSON stay out of the transcript."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 4000 or text[0] in "{[":
        return None
    lowered = text.lower()
    if lowered.startswith("select ") or "tool_use" in lowered or "tool_result" in lowered:
        return None
    return text


class PayloadError(Exception):
    def __init__(self, code: str, length: int, counts: dict[str, int]) -> None:
        super().__init__(code)
        self.code = code
        self.length = length
        self.counts = counts


def parse_assistant(payload: object, *, kind: str) -> dict:
    raw_length = _length(payload)
    document = _unwrap(payload)
    if not isinstance(document, dict):
        _fail("AGENT_RESPONSE_UNPARSEABLE", raw_length, {})
    if _message_error(document):
        _fail("AGENT_EXECUTION_ERROR", raw_length, {"error": 1})
    content = document.get("content")
    if not isinstance(content, list) or not content:
        _fail("AGENT_RESPONSE_UNPARSEABLE", raw_length, {})
    try:
        parsed = _scan(content)
    except PayloadError as exc:
        _fail(exc.code, raw_length, exc.counts)
    if not parsed["text"] and not parsed["queries"] and not parsed["uses"]:
        _fail("AGENT_RESPONSE_UNPARSEABLE", raw_length, parsed["counts"])
    cap = ANALYSIS_EVIDENCE_ROWS if kind == "analysis" else MAX_ROWS
    queries = [_finalize_query(query, cap) for query in parsed["queries"]]
    warnings = list(parsed["warnings"])
    if len(queries) > 1:
        warnings.append(_warning("MULTIPLE_QUERIES", "More than one query was returned."))
    if any(query["status"] == "error" for query in queries):
        warnings.append(_warning("QUERY_ERROR", "At least one query returned an error."))
    if any(query["truncated"] for query in queries):
        warnings.append(_warning("TRUNCATED", "At least one query was truncated."))
    if not queries:
        warnings.append(_warning("NO_QUERY_EXECUTED", "The agent did not run a query."))
    prose = "\n".join(part.strip() for part in parsed["text"] if part.strip())
    if kind == "analysis":
        result = {
            "kind": "analysis",
            "text": prose,
            "evidence": queries,
            "toolActivity": parsed["activity"],
            "suggestedFollowUps": parsed["suggestions"][:5],
            "notices": [{"code": "AGENT_GENERATED", "text": _AGENT_NOTICE}],
            "warnings": warnings,
        }
    else:
        primary = None
        for query in queries:
            if query["status"] == "success":
                primary = query["index"]
        intent, assumptions = _intent(prose)
        result = {
            "kind": "dataset",
            "interpretedIntent": intent,
            "assumptions": assumptions,
            "agentText": prose,
            "noQueryExecuted": not queries,
            "queries": queries,
            "primaryQueryIndex": primary,
            "warnings": warnings,
        }
    return _fit(result)


def _scan(content: list) -> dict:
    text: list[str] = []
    uses: dict[str, dict] = {}
    use_order: list[str] = []
    queries: list[dict] = []
    activity: list[dict] = []
    suggestions: list[str] = []
    warnings: list[dict] = []
    counts: dict[str, int] = {}
    matched: set[str] = set()
    errored: set[str] = set()
    for item in content:
        if not isinstance(item, dict):
            _count(counts, "unknown")
            logger.info("unsupported agent block type=non-dict")
            continue
        block_type = str(item.get("type") or "unknown")
        _count(counts, block_type)
        if block_type in {"text", "markdown"}:
            prose = _user_prose(item.get("text")) or _user_prose(item.get("content"))
            if prose:
                text.append(prose)
            continue
        if block_type == "thinking":
            continue
        if block_type == "suggested_queries":
            suggestions.extend(_strings(item))
            continue
        if block_type == "data_to_chart":
            activity.append(_activity(item, "data_to_chart", "NO_RESULT"))
            logger.info("agent chart block not rendered")
            continue
        if block_type == "tool_use":
            use = _tool_use(item)
            use_order.append(use["id"])
            uses[use["id"]] = use
            continue
        if block_type == "tool_result":
            result = _tool_result(item)
            use = uses.get(result["id"])
            if result["id"] and result["id"] in uses:
                matched.add(result["id"])
                if result["query"] is not None and result["query"]["status"] == "error":
                    errored.add(result["id"])
            elif result["query"] is not None or result["id"]:
                warnings.append(_warning("ORPHAN_TOOL_RESULT", "A tool result had no matching tool use."))
            if result["query"] is not None:
                query = result["query"]
                query["toolName"] = use["name"] if use else query.get("toolName")
                query["toolUseId"] = result["id"] or (use["id"] if use else "")
                queries.append(query)
            continue
        if block_type == "error":
            raise PayloadError("AGENT_EXECUTION_ERROR", 0, counts)
        prose = None
        if "tool_use" not in item and "tool_result" not in item and "sql" not in item and not isinstance(item.get("content"), (dict, list)):
            prose = _user_prose(item.get("text")) or _user_prose(item.get("content"))
        if prose:
            text.append(prose)
        else:
            logger.info("unsupported agent block type=%s", block_type)
    for use_id in use_order:
        use = uses[use_id]
        if use_id in errored:
            status = "ERROR"
        elif use_id in matched:
            status = "RESULT"
        else:
            status = "NO_RESULT"
            warnings.append(_warning("RESULT_NOT_RETURNED", "A tool use did not return a result."))
        if use["tool_type"] == "data_to_chart":
            logger.info("agent chart tool not rendered")
        activity.append(
            {
                "toolUseId": use_id,
                "toolType": use["tool_type"] or "unknown",
                "toolName": use["name"],
                "status": status,
            }
        )
    for index, query in enumerate(queries):
        query["index"] = index
    return {
        "text": text,
        "queries": queries,
        "uses": uses,
        "activity": activity,
        "suggestions": suggestions,
        "warnings": warnings,
        "counts": counts,
    }


def _tool_use(item: dict) -> dict:
    nested = item.get("tool_use") if isinstance(item.get("tool_use"), dict) else {}
    tool_id = _first_str(nested, item, "tool_use_id", "toolUseId", "id") or f"use-{id(item)}"
    name = _first_str(nested, item, "name")
    tool_type = _first_str(nested, item, "type", "tool_type", "toolType")
    if tool_type == "tool_use":
        tool_type = name
    return {"id": tool_id, "name": name, "tool_type": tool_type or name}


def _tool_result(item: dict) -> dict:
    nested = item.get("tool_result") if isinstance(item.get("tool_result"), dict) else None
    if nested is None and isinstance(item.get("tool_results"), dict):
        nested = item["tool_results"]
    body = nested or item
    tool_id = _first_str(body, item, "tool_use_id", "toolUseId", "id") or ""
    blocks = _json_blocks(body)
    if not blocks:
        return {"id": tool_id, "query": None}
    block = blocks[0]
    status_text = str(body.get("status") or block.get("status") or "").lower()
    error_value = body.get("error") if body.get("error") is not None else block.get("error")
    failed = status_text in {"error", "failed"} or error_value not in (None, "", [], {})
    query: dict[str, Any] = {
        "toolUseId": tool_id,
        "toolName": _first_str(body, block, "name", "tool_name"),
        "sql": block.get("sql") if isinstance(block.get("sql"), str) else None,
        "queryId": block.get("query_id") or block.get("queryId"),
        "status": "error" if failed else "success",
        "error": {"message": _error_message(error_value)[:500]} if failed else None,
        "columns": _columns(block),
        "rows": [] if failed else _rows(block),
        "rowCount": None if failed else _row_count(block),
        "extraWarnings": _result_warnings(body, block),
    }
    if query["queryId"] is not None:
        query["queryId"] = str(query["queryId"])
    return {"id": tool_id, "query": query}


def _finalize_query(query: dict, cap: int) -> dict:
    rows = list(query["rows"])
    row_count = query["rowCount"]
    truncated = False
    reason = None
    limit = None
    note = None
    if len(rows) > cap:
        rows = rows[:cap]
        truncated = True
        reason = "RESPONSE_CAP"
        limit = cap
        note = "The result was cut at the response cap. The full result remains in the thread."
    elif row_count is not None and len(rows) < row_count:
        truncated = True
        reason = "RESULT_SET_LIMIT"
        limit = row_count
        note = "The tool returned fewer rows than resultSetMetaData.numRows."
    else:
        limited = _limit_clause(query.get("sql"))
        if limited is not None and row_count == limited:
            truncated = True
            reason = "AGENT_ROW_LIMIT"
            limit = limited
            note = "The query ends with a row limit, so the total number of matching rows is unknown."
    status = query["status"]
    if status != "error" and not rows and (row_count in (0, None)):
        status = "empty"
    warnings = query.pop("extraWarnings", [])
    return {
        "index": query["index"],
        "toolUseId": query.get("toolUseId") or "",
        "toolName": query.get("toolName"),
        "sql": query.get("sql"),
        "queryId": query.get("queryId"),
        "status": status,
        "error": query.get("error"),
        "columns": query["columns"],
        "rows": rows,
        "rowCount": row_count,
        "rowsReturned": len(rows),
        "truncated": truncated,
        "truncation": {"reason": reason, "limit": limit, "note": note},
        "exportable": status != "error",
        "_warnings": warnings,
    }


def _fit(content: dict) -> dict:
    _attach_query_warnings(content)
    encoded = json.dumps(content, ensure_ascii=False).encode("utf-8")
    if len(encoded) <= MAX_MESSAGE_BYTES:
        return content
    bucket = content.get("queries") if content["kind"] == "dataset" else content.get("evidence")
    if isinstance(bucket, list):
        while bucket and len(json.dumps(content, ensure_ascii=False).encode("utf-8")) > MAX_MESSAGE_BYTES:
            longest = max(bucket, key=lambda query: len(query.get("rows") or []))
            rows = longest.get("rows") or []
            if not rows:
                break
            drop = max(1, len(rows) // 10)
            longest["rows"] = rows[:-drop]
            longest["rowsReturned"] = len(longest["rows"])
            longest["truncated"] = True
            longest["truncation"] = {
                "reason": "RESPONSE_CAP",
                "limit": MAX_ROWS,
                "note": "The result was cut at the response cap. The full result remains in the thread.",
            }
        _ensure_warning(content, "TRUNCATED", "At least one query was truncated.")
    return content


def _attach_query_warnings(content: dict) -> None:
    bucket = content.get("queries") if content.get("kind") == "dataset" else content.get("evidence")
    if not isinstance(bucket, list):
        return
    for query in bucket:
        extra = query.pop("_warnings", [])
        for warning in extra:
            if warning not in content["warnings"]:
                content["warnings"].append(warning)


def _json_blocks(body: dict) -> list[dict]:
    found: list[dict] = []
    content = body.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            raw = part.get("json")
            parsed = _coerce_json(raw)
            if isinstance(parsed, dict) and _is_sql_json(parsed):
                found.append(parsed)
    direct = body.get("json")
    parsed_direct = _coerce_json(direct)
    if isinstance(parsed_direct, dict) and _is_sql_json(parsed_direct):
        found.append(parsed_direct)
    if _is_sql_json(body):
        found.append(body)
    return found


def _is_sql_json(value: dict) -> bool:
    return any(key in value for key in ("sql", "result_set", "resultSet", "resultSetMetaData"))


def _columns(block: dict) -> list[dict]:
    meta = _metadata(block)
    row_type = meta.get("rowType") if isinstance(meta, dict) else None
    if not isinstance(row_type, list):
        return []
    columns = []
    for entry in row_type:
        if not isinstance(entry, dict):
            continue
        columns.append(
            {
                "name": str(entry.get("name") or ""),
                "type": str(entry.get("type") or ""),
                "nullable": _nullable(entry.get("nullable")),
                "scale": _scale(entry.get("scale")),
            }
        )
    return columns


def _rows(block: dict) -> list[list]:
    result_set = block.get("result_set") or block.get("resultSet")
    data = None
    if isinstance(result_set, dict):
        data = result_set.get("data")
    if data is None:
        data = block.get("data")
    if not isinstance(data, list):
        return []
    rows = []
    for row in data:
        if isinstance(row, list):
            rows.append([_cell(value) for value in row])
        else:
            rows.append([_cell(row)])
    return rows


def _row_count(block: dict) -> int | None:
    meta = _metadata(block)
    if not isinstance(meta, dict) or "numRows" not in meta:
        return None
    value = meta.get("numRows")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _metadata(block: dict) -> dict:
    result_set = block.get("result_set") or block.get("resultSet")
    if isinstance(result_set, dict) and isinstance(result_set.get("resultSetMetaData"), dict):
        return result_set["resultSetMetaData"]
    if isinstance(block.get("resultSetMetaData"), dict):
        return block["resultSetMetaData"]
    return {}


def _cell(value: object):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    try:
        if value == value.to_integral_value():  # type: ignore[attr-defined]
            return str(int(value))  # type: ignore[arg-type]
    except (AttributeError, ValueError):
        pass
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _intent(prose: str) -> tuple[str | None, list[str]]:
    sections = _sections(prose)
    intent = sections.get("interpreted intent")
    assumptions = _bullets(sections.get("assumptions") or "")
    return (intent or None), assumptions


def _sections(prose: str) -> dict[str, str]:
    matches = list(_HEADING.finditer(prose))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prose)
        sections[match.group(1).lower()] = prose[start:end].strip()
    if "interpreted intent" not in sections:
        inline = re.search(r"(?is)\*\*interpreted intent\*\*\s*(.+?)(?:\n\s*\*\*|\n\s*#|$)", prose)
        if inline:
            sections["interpreted intent"] = inline.group(1).strip()
    return sections


def _bullets(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        if line:
            lines.append(line[:400])
    return lines[:20]


def _strings(item: dict) -> list[str]:
    found: list[str] = []

    def walk(value: object) -> None:
        if len(found) >= 5:
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped and value is not item.get("type"):
                found.append(stripped[:200])
        elif isinstance(value, list):
            for entry in value:
                walk(entry)
        elif isinstance(value, dict):
            for key, entry in value.items():
                if key == "type":
                    continue
                walk(entry)

    walk(item.get("suggested_queries", item))
    return found[:5]


def _limit_clause(sql: object) -> int | None:
    if not isinstance(sql, str):
        return None
    match = _LIMIT.search(sql.strip())
    if not match:
        return None
    return int(match.group(1))


def _result_warnings(body: dict, block: dict) -> list[dict]:
    warnings = []
    for source in (body.get("warnings"), block.get("warnings")):
        if not isinstance(source, list):
            continue
        for entry in source:
            if isinstance(entry, str) and entry:
                warnings.append(_warning(entry, entry))
            elif isinstance(entry, dict) and entry.get("code"):
                warnings.append(
                    {"code": str(entry.get("code")), "message": str(entry.get("message") or entry.get("code"))}
                )
    return warnings


def _error_message(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("message", "error", "detail"):
            if isinstance(value.get(key), str):
                return value[key]
    if value in (None, "", [], {}):
        return "The query failed."
    return str(value)


def _nullable(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return None


def _scale(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _activity(item: dict, tool_type: str, status: str) -> dict:
    return {
        "toolUseId": _first_str(item, {}, "tool_use_id", "toolUseId", "id") or "",
        "toolType": tool_type,
        "toolName": _first_str(item, {}, "name"),
        "status": status,
    }


def _unwrap(payload: object) -> object:
    document = _coerce_json(payload)
    if isinstance(document, dict):
        nested = document.get("message_payload")
        if nested is None:
            nested = document.get("MESSAGE_PAYLOAD")
        if nested is not None:
            inner = _coerce_json(nested)
            if isinstance(inner, dict):
                return inner
    return document


def _coerce_json(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def _message_error(document: dict) -> bool:
    if isinstance(document.get("content"), list):
        return False
    status = str(document.get("status") or "").lower()
    return status in {"error", "failed"} or document.get("error") not in (None, "", [], {})


def _first_str(primary: dict, secondary: dict, *names: str) -> str | None:
    for source in (primary, secondary):
        if not isinstance(source, dict):
            continue
        for name in names:
            value = source.get(name)
            if isinstance(value, str) and value and value not in {"tool_use", "tool_result"}:
                return value
    return None


def _warning(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _ensure_warning(content: dict, code: str, message: str) -> None:
    if not any(item.get("code") == code for item in content["warnings"]):
        content["warnings"].append(_warning(code, message))


def _count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _length(payload: object) -> int:
    if isinstance(payload, str):
        return len(payload.encode("utf-8"))
    try:
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except TypeError:
        return 0


def _fail(code: str, length: int, counts: dict[str, int]) -> None:
    logger.info("agent payload unreadable bytes=%s blocks=%s code=%s", length, counts, code)
    raise PayloadError(code, length, counts)
