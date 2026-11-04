"""HMAC-signed conversation handles and run tokens. The token value is never logged."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass

from app.agents.clock import parse_utc
from app.agents.faults import ApiFault
from app.agents.registry import require_agent_key

_PREFIX = "v1"
_SIGNATURE_BYTES = 16
_DERIVATION = b"ma2-signing-v1"


@dataclass(frozen=True)
class ConversationClaims:
    thread_id: int
    agent_key: str
    created_at: str


@dataclass(frozen=True)
class RunClaims:
    thread_id: int
    agent_key: str
    user_message_id: str
    snowflake_run_id: str
    submitted_at: str


def signing_key(password: str) -> bytes:
    override = os.environ.get("V2_SIGNING_KEY")
    if override:
        return override.encode("utf-8")
    return hmac.new(password.encode("utf-8"), _DERIVATION, hashlib.sha256).digest()


def issue_conversation(*, thread_id: int, agent_key: str, created_at: str, key: bytes) -> str:
    payload = {
        "threadId": int(thread_id),
        "agentKey": require_agent_key(agent_key),
        "createdAt": created_at,
    }
    return _sign(payload, key)


def issue_run(
    *,
    thread_id: int,
    agent_key: str,
    user_message_id: int | str,
    snowflake_run_id: str,
    submitted_at: str,
    key: bytes,
) -> str:
    payload = {
        "threadId": int(thread_id),
        "agentKey": require_agent_key(agent_key),
        "userMessageId": str(int(user_message_id)),
        "snowflakeRunId": str(snowflake_run_id),
        "submittedAt": submitted_at,
    }
    return _sign(payload, key)


def verify_conversation(token: str, *, key: bytes) -> ConversationClaims:
    payload = _open(token, key, "CONVERSATION_NOT_FOUND")
    try:
        thread_id = payload["threadId"]
        agent_key = payload["agentKey"]
        created_at = payload["createdAt"]
        if isinstance(thread_id, bool) or not isinstance(thread_id, int):
            raise TypeError
        if not isinstance(created_at, str):
            raise TypeError
        require_agent_key(agent_key)
        parse_utc(created_at)
    except (ApiFault, KeyError, TypeError, ValueError):
        raise ApiFault(404, "CONVERSATION_NOT_FOUND", "Conversation was not found.") from None
    return ConversationClaims(thread_id=thread_id, agent_key=agent_key, created_at=created_at)


def verify_run(token: str, *, key: bytes) -> RunClaims:
    payload = _open(token, key, "RUN_NOT_FOUND")
    try:
        thread_id = payload["threadId"]
        agent_key = payload["agentKey"]
        user_message_id = payload["userMessageId"]
        snowflake_run_id = payload["snowflakeRunId"]
        submitted_at = payload["submittedAt"]
        if isinstance(thread_id, bool) or not isinstance(thread_id, int):
            raise TypeError
        if not isinstance(user_message_id, str) or not user_message_id.isdigit():
            raise TypeError
        if not isinstance(snowflake_run_id, str) or not snowflake_run_id:
            raise TypeError
        if not isinstance(submitted_at, str):
            raise TypeError
        require_agent_key(agent_key)
        parse_utc(submitted_at)
    except (ApiFault, KeyError, TypeError, ValueError):
        raise ApiFault(404, "RUN_NOT_FOUND", "Run was not found.") from None
    return RunClaims(
        thread_id=thread_id,
        agent_key=agent_key,
        user_message_id=user_message_id,
        snowflake_run_id=snowflake_run_id,
        submitted_at=submitted_at,
    )


def token_prefix(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def _sign(payload: dict, key: bytes) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hmac.new(key, body, hashlib.sha256).digest()[:_SIGNATURE_BYTES]
    return f"{_PREFIX}.{_b64(body)}.{_b64(digest)}"


def _open(token: str, key: bytes, code: str) -> dict:
    message = "Conversation was not found." if code == "CONVERSATION_NOT_FOUND" else "Run was not found."
    fault = ApiFault(404, code, message)
    if not isinstance(token, str):
        raise fault
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _PREFIX or not parts[1] or not parts[2]:
        raise fault
    try:
        body = _b64decode(parts[1])
        signature = _b64decode(parts[2])
    except (ValueError, UnicodeError):
        raise fault from None
    expected = hmac.new(key, body, hashlib.sha256).digest()[:_SIGNATURE_BYTES]
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        raise fault
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise fault from None
    if not isinstance(payload, dict):
        raise fault
    return payload


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
