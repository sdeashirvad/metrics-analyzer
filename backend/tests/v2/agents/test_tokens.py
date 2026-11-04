import base64
import json

import pytest

from app.agents.faults import ApiFault
from app.agents.tokens import issue_conversation, issue_run, signing_key, verify_conversation, verify_run

_KEY = b"test-signing-key"
_CREATED = "2026-11-04T00:00:00Z"


def test_conversation_and_run_round_trip():
    conversation = issue_conversation(thread_id=42, agent_key="analysis", created_at=_CREATED, key=_KEY)
    claims = verify_conversation(conversation, key=_KEY)
    assert claims.thread_id == 42
    assert claims.agent_key == "analysis"
    assert claims.created_at == _CREATED

    run = issue_run(
        thread_id=42,
        agent_key="data",
        user_message_id=8,
        snowflake_run_id="42-8",
        submitted_at=_CREATED,
        key=_KEY,
    )
    run_claims = verify_run(run, key=_KEY)
    assert run_claims.thread_id == 42
    assert run_claims.agent_key == "data"
    assert run_claims.user_message_id == "8"
    assert run_claims.snowflake_run_id == "42-8"
    assert run_claims.submitted_at == _CREATED
    assert "snow-secret-should-not-leak" not in conversation
    assert "snow-secret-should-not-leak" not in run


def test_tampered_conversation_is_not_found():
    token = issue_conversation(thread_id=42, agent_key="analysis", created_at=_CREATED, key=_KEY)
    tampered = _rewrite(token, lambda payload: payload.__setitem__("threadId", 43))
    with pytest.raises(ApiFault) as caught:
        verify_conversation(tampered, key=_KEY)
    assert caught.value.code == "CONVERSATION_NOT_FOUND"
    assert caught.value.status == 404


def test_tampered_run_is_not_found():
    token = issue_run(
        thread_id=42,
        agent_key="analysis",
        user_message_id="8",
        snowflake_run_id="42-8",
        submitted_at=_CREATED,
        key=_KEY,
    )
    tampered = _rewrite(token, lambda payload: payload.__setitem__("userMessageId", "9"))
    with pytest.raises(ApiFault) as caught:
        verify_run(tampered, key=_KEY)
    assert caught.value.code == "RUN_NOT_FOUND"

    head, _body, signature = token.partition(".")
    broken = f"{head}.{'A' if signature[:1] != 'A' else 'B'}{signature[1:]}"
    with pytest.raises(ApiFault) as signature_fault:
        verify_run(broken, key=_KEY)
    assert signature_fault.value.code == "RUN_NOT_FOUND"


def test_plain_thread_id_and_wrong_key_are_rejected():
    token = issue_conversation(thread_id=42, agent_key="analysis", created_at=_CREATED, key=_KEY)
    with pytest.raises(ApiFault) as plain:
        verify_conversation("42", key=_KEY)
    assert plain.value.code == "CONVERSATION_NOT_FOUND"
    with pytest.raises(ApiFault) as wrong_key:
        verify_conversation(token, key=b"other-key")
    assert wrong_key.value.code == "CONVERSATION_NOT_FOUND"


def test_signing_key_derivation(monkeypatch):
    monkeypatch.delenv("V2_SIGNING_KEY", raising=False)
    derived = signing_key("snow-secret-should-not-leak")
    assert signing_key("snow-secret-should-not-leak") == derived
    assert derived != b"snow-secret-should-not-leak"
    assert b"snow-secret-should-not-leak" not in derived
    monkeypatch.setenv("V2_SIGNING_KEY", "override-key")
    assert signing_key("snow-secret-should-not-leak") == b"override-key"


def _rewrite(token: str, mutate) -> str:
    version, body, signature = token.split(".")
    payload = json.loads(_decode(body))
    mutate(payload)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return f"{version}.{encoded}.{signature}"


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
