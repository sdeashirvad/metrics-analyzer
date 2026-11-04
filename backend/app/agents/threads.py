"""Snowflake thread calls. The SQL text is the call verified on 2026-11-04."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.agents.clock import as_int, format_utc, parse_utc
from app.agents.faults import ApiFault
from app.agents.thread_view import ThreadMessage, ThreadView

logger = logging.getLogger(__name__)

DATA_AGENT_RUN_SQL = "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(%(agent)s, %(body)s, TRUE)"
THREAD_MESSAGES_SQL = "SELECT SNOWFLAKE.CORTEX.THREAD_MESSAGES(%(tid)s)"


def first_run_body(text: str) -> dict:
    return {
        "messages": [{"role": "user", "content": [{"type": "text", "text": text}]}],
        "stream": False,
        "background": True,
    }


def follow_up_body(*, thread_id: int, parent_message_id: int, text: str) -> dict:
    thread = int(thread_id)
    parent = int(parent_message_id)
    if thread <= 0 or parent <= 0:
        raise ValueError("thread and parent ids must be positive")
    return {
        "thread_id": thread,
        "parent_message_id": parent,
        "background": True,
        "stream": False,
        "messages": [{"role": "user", "content": [{"type": "text", "text": text}]}],
    }


def submit_run(settings, agent_name: str, body: dict) -> dict:
    from app.db.connection import connect, dependency_failure, fetch_one

    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    try:
        with connect(settings) as connection:
            row = fetch_one(connection, DATA_AGENT_RUN_SQL, {"agent": agent_name, "body": payload})
    except Exception as exc:
        logger.info("agent submit failed error=%s", type(exc).__name__)
        if dependency_failure(exc):
            raise ApiFault(504, "UPSTREAM_TIMEOUT", "The data service timed out.", retryable=True) from exc
        raise ApiFault(502, "UPSTREAM_ERROR", "The data service could not complete the request.", retryable=True) from exc
    document = _coerce(_first_value(row))
    if not isinstance(document, dict):
        raise _bad_accept()
    status = str(document.get("status") or "").lower()
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    thread_id = as_int(_pick(metadata, "thread_id", "threadId"))
    user_message_id = as_int(_pick(metadata, "user_message_id", "userMessageId"))
    run_id = _pick(metadata, "run_id", "runId")
    if status not in {"in_progress", "completed"} or thread_id is None or user_message_id is None or not run_id:
        logger.info("agent submit rejected status=%s", status or "missing")
        raise _bad_accept()
    return {
        "thread_id": thread_id,
        "user_message_id": user_message_id,
        "run_id": str(run_id),
        "status": status,
    }


def read_thread(settings, thread_id: int) -> ThreadView:
    from app.db.connection import connect, fetch_all

    try:
        with connect(settings) as connection:
            rows = fetch_all(connection, THREAD_MESSAGES_SQL, {"tid": int(thread_id)})
    except Exception as exc:
        logger.info("thread read failed error=%s", type(exc).__name__)
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True) from exc
    return normalize(rows)


def normalize(raw: object) -> ThreadView:
    if raw is None:
        return _empty()
    if isinstance(raw, list):
        if len(raw) == 1:
            parsed = _as_document(raw[0])
            if parsed is not None and not (_is_message(raw[0]) and not _is_thread(parsed)):
                view = _from_any(parsed)
                if view.present or _is_thread(parsed) or isinstance(parsed, list):
                    return view
        messages: list[ThreadMessage] = []
        for row in raw:
            if isinstance(row, dict) and (_is_message(row) or _is_thread(row)):
                if _is_thread(row) and not _is_message(row):
                    return _from_thread(row)
                messages.append(_message(row))
                continue
            parsed = _as_document(row)
            if isinstance(parsed, dict) and _is_thread(parsed):
                return _from_thread(parsed)
            if isinstance(parsed, dict) and _is_message(parsed):
                messages.append(_message(parsed))
        return ThreadView(None, None, messages, None, None)
    return _from_any(_coerce(raw))


def _from_any(value: object) -> ThreadView:
    if isinstance(value, list):
        messages = [_message(item) for item in value if isinstance(item, dict)]
        return ThreadView(None, None, messages, None, None)
    if isinstance(value, dict) and _is_thread(value):
        return _from_thread(value)
    if isinstance(value, dict) and _is_message(value):
        return ThreadView(None, None, [_message(value)], None, None)
    return _empty()


def _from_thread(document: dict) -> ThreadView:
    metadata = _pick(document, "metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    status = _pick(metadata, "status")
    if status is None:
        status = _pick(document, "status")
    if isinstance(status, str):
        status = status.upper()
    else:
        status = None
    last = as_int(_pick(metadata, "last_message_id", "lastMessageId"))
    if last is None:
        last = as_int(_pick(document, "last_message_id", "lastMessageId"))
    raw_messages = _pick(document, "messages")
    if isinstance(raw_messages, dict):
        raw_messages = [raw_messages]
    messages = []
    if isinstance(raw_messages, list):
        messages = [_message(item) for item in raw_messages if isinstance(item, dict)]
    created = _time(_pick(metadata, "created_on", "created_at", "createdOn") or _pick(document, "created_on", "created_at"))
    updated = _time(_pick(metadata, "updated_on", "updated_at", "updatedOn") or _pick(document, "updated_on", "updated_at"))
    return ThreadView(status, last, messages, created, updated)


def _message(row: dict) -> ThreadMessage:
    payload = _coerce(_pick(row, "message_payload", "messagePayload", "payload"))
    if not isinstance(payload, dict) and isinstance(row.get("content"), list):
        payload = row
    role_value = _pick(row, "role")
    if role_value is None and isinstance(payload, dict):
        role_value = payload.get("role")
    agent = _pick(row, "agent")
    if agent is None and isinstance(payload, dict):
        agent = payload.get("agent")
    if isinstance(agent, dict):
        agent_name = agent.get("name") if isinstance(agent.get("name"), str) else None
    elif isinstance(agent, str):
        agent_name = agent
    else:
        agent_name = None
    return ThreadMessage(
        message_id=as_int(_pick(row, "message_id", "messageId", "id")) or 0,
        parent_id=as_int(_pick(row, "parent_id", "parentId")),
        role=str(role_value or "").lower(),
        created_at=_time(_pick(row, "created_on", "created_at", "timestamp", "createdOn")),
        payload=payload,
        agent_name=agent_name,
    )


def _as_document(row: object) -> object | None:
    if isinstance(row, dict) and (_is_thread(row) or _is_message(row)):
        return row
    if isinstance(row, dict) and len(row) == 1:
        return _coerce(next(iter(row.values())))
    return _coerce(row)


def _is_thread(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    keys = {str(key).lower() for key in value}
    return "messages" in keys or "metadata" in keys


def _is_message(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    keys = {str(key).lower() for key in value}
    return "message_payload" in keys or "messagepayload" in keys or ("role" in keys and "content" in keys)


def _pick(mapping: object, *names: str):
    if not isinstance(mapping, dict):
        return None
    folded = {str(key).lower(): value for key, value in mapping.items()}
    for name in names:
        if name.lower() in folded and folded[name.lower()] is not None:
            return folded[name.lower()]
    return None


def _first_value(row: object):
    if isinstance(row, dict) and row:
        return next(iter(row.values()))
    return row


def _coerce(value: object):
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value
    return value


def _time(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return format_utc(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    if " " in candidate and "T" not in candidate:
        candidate = candidate.replace(" ", "T", 1)
    try:
        return format_utc(parse_utc(candidate))
    except ValueError:
        return text


def _empty() -> ThreadView:
    return ThreadView(None, None, [], None, None)


def _bad_accept() -> ApiFault:
    return ApiFault(502, "UPSTREAM_ERROR", "The data service could not complete the request.", retryable=True)
