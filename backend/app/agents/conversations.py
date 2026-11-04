"""Create a thread, continue it, and read run state back from THREAD_MESSAGES."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid

from app.agents.clock import format_utc, parse_utc, utc_now
from app.agents.context.builder import build_preview
from app.agents.context.render import chips_from_ref, compose_first_message, hashes_match, ma2_ref, read_user_message
from app.agents.export import csv_document
from app.agents.faults import ApiFault
from app.agents.limits import memory
from app.agents.parse import PayloadError, parse_assistant
from app.agents.registry import MAX_USER_MESSAGES, is_other_agent, response_kind, snowflake_agent
from app.agents.runs import derive_run, same_id
from app.agents.threads import first_run_body, follow_up_body, read_thread, submit_run
from app.agents.tokens import issue_conversation, issue_run, token_prefix, verify_conversation, verify_run

logger = logging.getLogger(__name__)

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")
_NOTICE = "Agent-generated. Explanations of cause are hypotheses until validated."


def request_fingerprint(scope: str, payload: dict) -> str:
    material = json.dumps({"scope": scope, "body": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def create_conversation(settings, body: dict, key: bytes) -> tuple[int, dict]:
    agent_key = body["agentKey"]
    question = _clean_message(body.get("message"))
    _client_request(body.get("clientRequestId"))
    reviewed = body.get("contextHash")
    if not isinstance(reviewed, str) or not _HASH.fullmatch(reviewed):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    preview = build_preview(body["context"])
    if not hashes_match(preview["contextHash"], reviewed):
        raise ApiFault(409, "CONTEXT_STALE", "The context changed since it was reviewed.")
    created_at = format_utc(utc_now())
    scope = preview["scope"]
    ref = ma2_ref(
        agent_key=agent_key,
        client_request_id=body["clientRequestId"],
        context_hash=preview["contextHash"],
        definitions_version=preview["definitionsVersion"],
        entry_surface=preview["entrySurface"],
        month=scope["month"],
        month_source=scope["monthSource"],
        metric_id=scope["metricId"],
        eon_id=scope["eonId"],
        created_at=created_at,
    )
    text = compose_first_message(
        rendered=preview["rendered"]["text"],
        entry_surface=preview["entrySurface"],
        month=scope["month"],
        metric_id=scope["metricId"],
        eon_id=scope["eonId"],
        filters=scope["filters"],
        question=question,
        ref=ref,
    )
    reservation, accepted = _execute(settings, "create", None, snowflake_agent(agent_key), first_run_body(text))
    handle = issue_conversation(thread_id=accepted["thread_id"], agent_key=agent_key, created_at=created_at, key=key)
    run_token = _bind_run(reservation, accepted, handle, agent_key, created_at, key)
    run = _fresh_run(run_token, handle, agent_key, accepted["user_message_id"], created_at)
    _log(run_token, agent_key, run)
    conversation = {
        "conversationId": handle,
        "threadId": accepted["thread_id"],
        "agentKey": agent_key,
        "title": question[:60],
        "entrySurface": preview["entrySurface"],
        "scope": {"month": scope["month"], "metricId": scope["metricId"], "eonId": scope["eonId"]},
        "chips": preview["chips"],
        "contextHash": preview["contextHash"],
        "messageCount": 1,
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    return 202, {
        "conversation": conversation,
        "userMessage": _user_message(accepted["user_message_id"], handle, agent_key, run_token, created_at, question, preview["contextHash"]),
        "run": run,
    }


def send_message(settings, conversation_id: str, body: dict, key: bytes) -> tuple[int, dict]:
    claims = verify_conversation(conversation_id, key=key)
    question = _clean_message(body.get("message"))
    _client_request(body.get("clientRequestId"))
    view = _load(settings, claims.thread_id, force=True)
    _require_present(view)
    _ensure_agent(view, claims.agent_key)
    _ensure_idle(view, claims.thread_id, claims.agent_key, key)
    _ensure_room(view)
    parent = view.last_message_id
    if parent is None or parent <= 0:
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True)
    try:
        payload = follow_up_body(thread_id=claims.thread_id, parent_message_id=parent, text=question)
    except ValueError as exc:
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True) from exc
    reservation, accepted = _execute(settings, "followup", conversation_id, snowflake_agent(claims.agent_key), payload)
    submitted = format_utc(utc_now())
    run_token = _bind_run(reservation, accepted, conversation_id, claims.agent_key, submitted, key)
    run = _fresh_run(run_token, conversation_id, claims.agent_key, accepted["user_message_id"], submitted)
    _log(run_token, claims.agent_key, run)
    return 202, {
        "userMessage": _user_message(accepted["user_message_id"], conversation_id, claims.agent_key, run_token, submitted, question, None),
        "run": run,
    }


def get_conversation(settings, conversation_id: str, key: bytes) -> dict:
    claims = verify_conversation(conversation_id, key=key)
    view = _load(settings, claims.thread_id, force=False)
    _require_present(view)
    _ensure_agent(view, claims.agent_key)
    return {
        "conversation": _conversation_from_thread(view, conversation_id, claims),
        "messages": _public_messages(view, conversation_id, claims.thread_id, claims.agent_key, claims.created_at, key),
        "activeRun": _active_run(view, conversation_id, claims.thread_id, claims.agent_key, key),
    }


def get_context(settings, conversation_id: str, key: bytes) -> dict:
    claims = verify_conversation(conversation_id, key=key)
    view = _load(settings, claims.thread_id, force=False)
    _require_present(view)
    oldest = _oldest_user(view)
    info = read_user_message(oldest.payload if oldest else "")
    return {"chips": chips_from_ref(info["ref"]), "lines": info["lines"]}


def get_run(settings, run_id: str, key: bytes) -> dict:
    claims = verify_run(run_id, key=key)
    view = _load(settings, claims.thread_id, force=False)
    if not view.present:
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True)
    _ensure_agent(view, claims.agent_key)
    conversation_id = _handle_for(view, claims.thread_id, claims.agent_key, key, claims.submitted_at)
    attempt, retry_of = _attempt(view, claims.user_message_id)
    run = derive_run(
        run_id=run_id,
        conversation_id=conversation_id,
        agent_key=claims.agent_key,
        user_message_id=claims.user_message_id,
        submitted_at=claims.submitted_at,
        messages=view.messages,
        thread_status=view.status,
        now=utc_now(),
        attempt=attempt,
        retry_of=retry_of,
    )
    if run["status"] != "RUNNING":
        memory.note_terminal(claims.snowflake_run_id)
    _remember_parsed(claims.thread_id, run)
    _log(run_id, claims.agent_key, run)
    return run


def retry_run(settings, run_id: str, key: bytes) -> tuple[int, dict]:
    claims = verify_run(run_id, key=key)
    view = _load(settings, claims.thread_id, force=True)
    if not view.present:
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True)
    _ensure_agent(view, claims.agent_key)
    conversation_id = _handle_for(view, claims.thread_id, claims.agent_key, key, claims.submitted_at)
    existing = _retry_message(view, claims.snowflake_run_id)
    if existing is not None:
        return 200, {"run": _run_for_message(view, existing, conversation_id, claims.thread_id, claims.agent_key, key)}
    current = derive_run(
        run_id=run_id,
        conversation_id=conversation_id,
        agent_key=claims.agent_key,
        user_message_id=claims.user_message_id,
        submitted_at=claims.submitted_at,
        messages=view.messages,
        thread_status=view.status,
        now=utc_now(),
    )
    if current["status"] != "FAILED" or not (current["error"] or {}).get("retryable"):
        raise ApiFault(409, "RUN_NOT_RETRYABLE", "This run cannot be retried.")
    newest = next((message for message in view.messages if message.role == "user"), None)
    if newest is None or not same_id(newest.message_id, claims.user_message_id):
        raise ApiFault(409, "RUN_NOT_RETRYABLE", "This run cannot be retried.")
    _ensure_room(view)
    original = _find(view, claims.user_message_id)
    question = read_user_message(original.payload)["text"] if original else ""
    if not question:
        raise ApiFault(409, "RUN_NOT_RETRYABLE", "This run cannot be retried.")
    oldest = _oldest_user(view)
    ref = read_user_message(oldest.payload)["ref"] if oldest else {}
    parent = int(claims.user_message_id)
    if _child_exists(view, claims.user_message_id, claims.agent_key):
        parent = view.last_message_id or parent
    text = question + "\n" + _retry_ref(claims, ref)
    try:
        payload = follow_up_body(thread_id=claims.thread_id, parent_message_id=parent, text=text)
    except ValueError as exc:
        raise ApiFault(503, "THREAD_UNAVAILABLE", "The conversation thread could not be read.", retryable=True) from exc
    reservation, accepted = _execute(settings, "retry", conversation_id, snowflake_agent(claims.agent_key), payload)
    submitted = format_utc(utc_now())
    run_token = _bind_run(reservation, accepted, conversation_id, claims.agent_key, submitted, key)
    run = _fresh_run(
        run_token,
        conversation_id,
        claims.agent_key,
        accepted["user_message_id"],
        submitted,
        attempt=2,
        retry_of=claims.snowflake_run_id,
    )
    _log(run_token, claims.agent_key, run)
    return 202, {"run": run}


def export_query(settings, conversation_id: str, message_id: str, index: int, key: bytes) -> tuple[str, str]:
    claims = verify_conversation(conversation_id, key=key)
    if index < 0:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    content = memory.cached_parse(claims.thread_id, str(message_id))
    if content is None:
        view = _load(settings, claims.thread_id, force=True)
        _require_present(view)
        message = _find(view, message_id)
        if message is None or message.role != "assistant":
            raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
        try:
            content = parse_assistant(message.payload, kind=response_kind(claims.agent_key))
        except PayloadError as exc:
            raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.") from exc
        memory.store_parse(claims.thread_id, str(message.message_id), content)
    bucket = content.get("queries") if content.get("kind") == "dataset" else content.get("evidence")
    if not isinstance(bucket, list) or index >= len(bucket):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    query = bucket[index]
    return csv_document(
        query.get("columns") or [],
        query.get("rows") or [],
        index=index,
        partial=bool(query.get("truncated")),
    )


def _execute(settings, kind: str, handle: str | None, agent_name: str, body: dict):
    reservation = memory.reserve(kind, handle)
    try:
        accepted = submit_run(settings, agent_name, body)
    except ApiFault as exc:
        memory.release(reservation)
        if exc.status in {502, 503, 504}:
            memory.note_failure()
        raise
    except Exception:
        memory.release(reservation)
        memory.note_failure()
        raise
    return reservation, accepted


def _bind_run(reservation: str, accepted: dict, handle: str, agent_key: str, submitted_at: str, key: bytes) -> str:
    run_token = issue_run(
        thread_id=accepted["thread_id"],
        agent_key=agent_key,
        user_message_id=accepted["user_message_id"],
        snowflake_run_id=accepted["run_id"],
        submitted_at=submitted_at,
        key=key,
    )
    memory.fulfill(
        reservation,
        snowflake_run_id=accepted["run_id"],
        run_token=run_token,
        thread_id=accepted["thread_id"],
        user_message_id=str(accepted["user_message_id"]),
        handle=handle,
    )
    memory.drop_thread(accepted["thread_id"])
    return run_token


def _load(settings, thread_id: int, *, force: bool):
    if not force:
        cached = memory.cached_thread(thread_id)
        if cached is not None:
            return cached
    view = read_thread(settings, thread_id)
    memory.store_thread(thread_id, view)
    return view


def _require_present(view) -> None:
    if not view.present:
        raise ApiFault(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.")


def _ensure_agent(view, agent_key: str) -> None:
    for message in view.messages:
        if is_other_agent(message.agent_name, agent_key):
            raise ApiFault(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.")


def _ensure_idle(view, thread_id: int, agent_key: str, key: bytes) -> None:
    if (view.status or "").upper() != "IN_PROGRESS":
        return
    newest = next((message for message in view.messages if message.role == "user"), None)
    token = memory.active_token(thread_id)
    if token is None and newest is not None:
        token = _token_for(thread_id, agent_key, newest, key)
    raise ApiFault(
        409,
        "RUN_IN_PROGRESS",
        "A run is already in progress for this conversation.",
        details={"runId": token} if token else None,
    )


def _ensure_room(view) -> None:
    if sum(1 for message in view.messages if message.role == "user") >= MAX_USER_MESSAGES:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.", details={"reason": "CONVERSATION_LIMIT"})


def _public_messages(view, conversation_id: str, thread_id: int, agent_key: str, created_at: str, key: bytes) -> list[dict]:
    ordered = list(reversed(view.messages))
    if len(ordered) > 26:
        ordered = ordered[-26:]
    messages = []
    for message in ordered:
        if message.role == "user":
            info = read_user_message(message.payload)
            messages.append(
                _user_message(
                    message.message_id,
                    conversation_id,
                    agent_key,
                    _token_for(thread_id, agent_key, message, key),
                    message.created_at or created_at,
                    info["text"],
                    info["ref"].get("ctx"),
                )
            )
            continue
        if message.role != "assistant" or is_other_agent(message.agent_name, agent_key):
            continue
        content = _content_or_warning(message.payload, agent_key)
        parent = _find(view, message.parent_id) if message.parent_id is not None else None
        messages.append(
            {
                "messageId": str(message.message_id),
                "conversationId": conversation_id,
                "role": "assistant",
                "agentKey": agent_key,
                "runId": _token_for(thread_id, agent_key, parent, key) if parent else None,
                "createdAt": message.created_at or created_at,
                "content": content,
            }
        )
        memory.store_parse(thread_id, str(message.message_id), content)
    return messages


def _conversation_from_thread(view, conversation_id: str, claims) -> dict:
    oldest = _oldest_user(view)
    info = read_user_message(oldest.payload) if oldest else {"text": "", "ref": {}}
    ref = info["ref"]
    metric = ref.get("metric") if ref.get("metric") not in (None, "-", "") else None
    eon = ref.get("application") if ref.get("application") not in (None, "-", "") else None
    created = ref.get("created") or view.created_at or claims.created_at
    updated = view.updated_at or (view.messages[0].created_at if view.messages else created)
    return {
        "conversationId": conversation_id,
        "threadId": claims.thread_id,
        "agentKey": claims.agent_key,
        "title": (info["text"] or "Conversation")[:60],
        "entrySurface": ref.get("surface") or "general",
        "scope": {"month": ref.get("month") or "", "metricId": metric, "eonId": eon},
        "chips": chips_from_ref(ref),
        "contextHash": ref.get("ctx") or "",
        "messageCount": len(view.messages),
        "createdAt": created,
        "updatedAt": updated or created,
    }


def _active_run(view, conversation_id: str, thread_id: int, agent_key: str, key: bytes):
    newest = next((message for message in view.messages if message.role == "user"), None)
    if newest is None or _child_exists(view, newest.message_id, agent_key):
        return None
    return _run_for_message(view, newest, conversation_id, thread_id, agent_key, key)


def _run_for_message(view, message, conversation_id: str, thread_id: int, agent_key: str, key: bytes) -> dict:
    submitted = message.created_at or format_utc(utc_now())
    try:
        parse_utc(submitted)
    except ValueError:
        submitted = format_utc(utc_now())
    token = memory.remembered_run(thread_id, str(message.message_id)) or issue_run(
        thread_id=thread_id,
        agent_key=agent_key,
        user_message_id=message.message_id,
        snowflake_run_id=f"{thread_id}-{int(message.message_id)}",
        submitted_at=submitted,
        key=key,
    )
    attempt, retry_of = _attempt(view, message.message_id)
    run = derive_run(
        run_id=token,
        conversation_id=conversation_id,
        agent_key=agent_key,
        user_message_id=str(message.message_id),
        submitted_at=submitted,
        messages=view.messages,
        thread_status=view.status,
        now=utc_now(),
        attempt=attempt,
        retry_of=retry_of,
    )
    _remember_parsed(thread_id, run)
    return run


def _token_for(thread_id: int, agent_key: str, message, key: bytes) -> str:
    remembered = memory.remembered_run(thread_id, str(message.message_id))
    if remembered:
        return remembered
    submitted = message.created_at or format_utc(utc_now())
    try:
        parse_utc(submitted)
    except ValueError:
        submitted = format_utc(utc_now())
    return issue_run(
        thread_id=thread_id,
        agent_key=agent_key,
        user_message_id=message.message_id,
        snowflake_run_id=f"{thread_id}-{int(message.message_id)}",
        submitted_at=submitted,
        key=key,
    )


def _handle_for(view, thread_id: int, agent_key: str, key: bytes, fallback_created: str) -> str:
    oldest = _oldest_user(view)
    created = fallback_created
    if oldest is not None:
        stamped = read_user_message(oldest.payload)["ref"].get("created")
        if stamped:
            created = stamped
    try:
        parse_utc(created)
    except ValueError:
        created = fallback_created
    return issue_conversation(thread_id=thread_id, agent_key=agent_key, created_at=created, key=key)


def _attempt(view, user_message_id) -> tuple[int, str | None]:
    attempt = 1
    retry_of = None
    current = str(int(user_message_id)) if str(user_message_id).isdigit() else str(user_message_id)
    target = current
    seen: set[str] = set()
    for _ in range(8):
        message = _find(view, current)
        if message is None or message.role != "user":
            break
        prior = read_user_message(message.payload)["ref"].get("retry-of")
        if current == target:
            retry_of = prior or None
        if not prior or prior in seen:
            break
        seen.add(prior)
        attempt += 1
        suffix = prior.rsplit("-", 1)[-1]
        if not suffix.isdigit():
            break
        current = suffix
    return attempt, retry_of


def _retry_ref(claims, ref: dict) -> str:
    metric = ref.get("metric")
    application = ref.get("application")
    return ma2_ref(
        agent_key=claims.agent_key,
        client_request_id=str(uuid.uuid4()),
        context_hash=ref.get("ctx") or "000000000000",
        definitions_version=ref.get("definitions") or "",
        entry_surface=ref.get("surface") or "general",
        month=ref.get("month") or "-",
        month_source=ref.get("monthSource") or "selected",
        metric_id=None if metric in (None, "-", "") else metric,
        eon_id=None if application in (None, "-", "") else application,
        retry_of=claims.snowflake_run_id,
    )


def _retry_message(view, snowflake_run_id: str):
    for message in view.messages:
        if message.role == "user" and read_user_message(message.payload)["ref"].get("retry-of") == snowflake_run_id:
            return message
    return None


def _child_exists(view, user_message_id, agent_key: str) -> bool:
    return any(
        message.role == "assistant" and same_id(message.parent_id, user_message_id) and not is_other_agent(message.agent_name, agent_key)
        for message in view.messages
    )


def _find(view, message_id):
    for message in view.messages:
        if same_id(message.message_id, message_id):
            return message
    return None


def _oldest_user(view):
    users = [message for message in view.messages if message.role == "user"]
    if not users:
        return None
    return users[-1]


def _content_or_warning(payload, agent_key: str) -> dict:
    try:
        return parse_assistant(payload, kind=response_kind(agent_key))
    except PayloadError as exc:
        warning = {"code": exc.code, "message": "The agent response could not be read."}
        if response_kind(agent_key) == "analysis":
            return {
                "kind": "analysis",
                "text": "",
                "evidence": [],
                "toolActivity": [],
                "suggestedFollowUps": [],
                "notices": [{"code": "AGENT_GENERATED", "text": _NOTICE}],
                "warnings": [warning],
            }
        return {
            "kind": "dataset",
            "interpretedIntent": None,
            "assumptions": [],
            "agentText": "",
            "noQueryExecuted": True,
            "queries": [],
            "primaryQueryIndex": None,
            "warnings": [warning],
        }


def _fresh_run(run_token, conversation_id, agent_key, user_message_id, submitted_at, attempt: int = 1, retry_of: str | None = None) -> dict:
    return derive_run(
        run_id=run_token,
        conversation_id=conversation_id,
        agent_key=agent_key,
        user_message_id=str(user_message_id),
        submitted_at=submitted_at,
        messages=[],
        thread_status="IN_PROGRESS",
        now=parse_utc(submitted_at),
        attempt=attempt,
        retry_of=retry_of,
    )


def _user_message(message_id, conversation_id, agent_key, run_id, created_at, text, context_hash) -> dict:
    return {
        "messageId": str(message_id),
        "conversationId": conversation_id,
        "role": "user",
        "agentKey": agent_key,
        "runId": run_id,
        "createdAt": created_at,
        "content": {"kind": "user", "text": text, "contextHash": context_hash},
    }


def _remember_parsed(thread_id: int, run: dict) -> None:
    message = run.get("message") or {}
    content = message.get("content")
    if message.get("messageId") and isinstance(content, dict):
        memory.store_parse(thread_id, str(message["messageId"]), content)


def _log(run_id: str, agent_key: str, run: dict) -> None:
    if not memory.status_changed(token_prefix(run_id), run["status"]):
        return
    content = (run.get("message") or {}).get("content") or {}
    bucket = content.get("queries") or content.get("evidence") or []
    query_ids = [item["queryId"] for item in bucket if isinstance(item, dict) and item.get("queryId")]
    logger.info(
        "agent run run=%s agentKey=%s status=%s elapsedMs=%s tools=%s queries=%s",
        token_prefix(run_id),
        agent_key,
        run["status"],
        run.get("elapsedMs"),
        len(bucket),
        ",".join(query_ids),
    )


def _clean_message(value: object) -> str:
    if not isinstance(value, str):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    text = value.strip()
    if not text:
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
    if len(text) > 2000:
        raise ApiFault(400, "MESSAGE_TOO_LONG", "The message is too long.")
    return text


def _client_request(value: object) -> None:
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise ApiFault(400, "VALIDATION_FAILED", "The request is not valid.")
