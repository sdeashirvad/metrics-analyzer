"""Run state is a function of the token, the clock, and the thread."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.agents.clock import format_utc, parse_utc
from app.agents.parse import PayloadError, parse_assistant
from app.agents.registry import FAIL_AFTER_MS, OVERDUE_AFTER_MS, is_other_agent, response_kind
from app.agents.thread_view import ThreadMessage

_ERRORS = {
    "AGENT_TIMEOUT": "The agent did not answer in time.",
    "AGENT_EXECUTION_ERROR": "The agent could not finish this run.",
    "AGENT_RESPONSE_UNPARSEABLE": "The agent response could not be read.",
}


def derive_run(
    *,
    run_id: str,
    conversation_id: str,
    agent_key: str,
    user_message_id: str,
    submitted_at: str,
    messages: list[ThreadMessage],
    thread_status: str | None,
    now: datetime,
    attempt: int = 1,
    retry_of: str | None = None,
) -> dict:
    submitted = parse_utc(submitted_at)
    elapsed = max(0, int((now - submitted).total_seconds() * 1000))
    child = _child(messages, user_message_id, agent_key)
    finished_at = None
    error = None
    message = None
    if child is not None:
        finished_at = child.created_at or format_utc(now)
        try:
            content = parse_assistant(child.payload, kind=response_kind(agent_key))
        except PayloadError as exc:
            status = "FAILED"
            error = _error(exc.code)
            finished_at = format_utc(now)
        else:
            status = "COMPLETED"
            message = _assistant_message(child, conversation_id, agent_key, run_id, finished_at, content)
    elif elapsed >= FAIL_AFTER_MS:
        status = "FAILED"
        error = _error("AGENT_TIMEOUT")
        finished_at = format_utc(now)
    elif (thread_status or "").upper() == "IDLE":
        status = "FAILED"
        error = _error("AGENT_EXECUTION_ERROR")
        finished_at = format_utc(now)
    else:
        status = "RUNNING"
    overdue = status == "RUNNING" and elapsed >= OVERDUE_AFTER_MS
    relevant = _span(submitted, finished_at) if status == "COMPLETED" and finished_at else elapsed
    return {
        "runId": run_id,
        "conversationId": conversation_id,
        "agentKey": agent_key,
        "status": status,
        "overdue": overdue,
        "attempt": attempt,
        "retryOf": retry_of,
        "submittedAt": format_utc(submitted),
        "finishedAt": finished_at if status != "RUNNING" else None,
        "elapsedMs": elapsed if status != "COMPLETED" else relevant,
        "pollAfterMs": _poll(elapsed, status),
        "events": _events(submitted, status, relevant, finished_at, error),
        "error": error,
        "message": message,
    }


def same_id(left: object, right: object) -> bool:
    from app.agents.clock import as_int

    left_id = as_int(left)
    right_id = as_int(right)
    if left_id is not None and right_id is not None:
        return left_id == right_id
    return str(left) == str(right)


def _child(messages: list[ThreadMessage], user_message_id: str, agent_key: str) -> ThreadMessage | None:
    for message in messages:
        if message.role != "assistant":
            continue
        if not same_id(message.parent_id, user_message_id):
            continue
        if is_other_agent(message.agent_name, agent_key):
            continue
        return message
    return None


def _assistant_message(message, conversation_id, agent_key, run_id, created_at, content) -> dict:
    return {
        "messageId": str(message.message_id),
        "conversationId": conversation_id,
        "role": "assistant",
        "agentKey": agent_key,
        "runId": run_id,
        "createdAt": created_at,
        "content": content,
    }


def _error(code: str) -> dict:
    return {"code": code, "message": _ERRORS.get(code, "The agent could not finish this run."), "retryable": True}


def _poll(elapsed: int, status: str) -> int | None:
    if status != "RUNNING":
        return None
    if elapsed < 10_000:
        return 1500
    if elapsed < 60_000:
        return 3000
    return 5000


def _events(submitted: datetime, status: str, relevant: int, finished_at: str | None, error: dict | None) -> list[dict]:
    submitted_at = format_utc(submitted)
    events = [
        {"at": submitted_at, "type": "submitted"},
        {"at": submitted_at, "type": "running"},
    ]
    if relevant >= OVERDUE_AFTER_MS:
        events.append({"at": format_utc(submitted + timedelta(milliseconds=OVERDUE_AFTER_MS)), "type": "overdue"})
    if status == "COMPLETED" and finished_at:
        events.append({"at": finished_at, "type": "completed"})
    elif status == "FAILED":
        failed = {"at": finished_at or format_utc(submitted), "type": "failed"}
        if error:
            failed["detail"] = error["code"]
        events.append(failed)
    return events


def _span(submitted: datetime, finished_at: str) -> int:
    try:
        return max(0, int((parse_utc(finished_at) - submitted).total_seconds() * 1000))
    except ValueError:
        return 0
