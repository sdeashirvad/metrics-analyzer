import json

from app.agents.threads import DATA_AGENT_RUN_SQL, THREAD_MESSAGES_SQL, first_run_body, follow_up_body, normalize
import pytest


def test_first_message_body_has_no_thread():
    body = first_run_body("How many applications reported?")
    assert "thread_id" not in body
    assert "parent_message_id" not in body
    assert body["stream"] is False
    assert body["background"] is True
    assert body["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "How many applications reported?"}]}
    ]


def test_follow_up_uses_integer_ids():
    body = follow_up_body(thread_id=42, parent_message_id=7, text="And by tier?")
    assert body["thread_id"] == 42
    assert body["parent_message_id"] == 7
    assert isinstance(body["thread_id"], int)
    assert isinstance(body["parent_message_id"], int)
    assert body["stream"] is False
    assert body["background"] is True
    with pytest.raises(ValueError):
        follow_up_body(thread_id=42, parent_message_id=0, text="no")


def test_sql_is_the_verified_call():
    assert DATA_AGENT_RUN_SQL == "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(%(agent)s, %(body)s, TRUE)"
    assert THREAD_MESSAGES_SQL == "SELECT SNOWFLAKE.CORTEX.THREAD_MESSAGES(%(tid)s)"


def test_normalize_keeps_listed_order_and_parses_compressed_payload():
    assistant = {"role": "assistant", "content": [{"type": "text", "text": "done"}]}
    document = {
        "metadata": {"status": "IDLE", "last_message_id": 4},
        "messages": [
            {
                "message_id": 4,
                "parent_id": 20,
                "role": "assistant",
                "is_compressed": True,
                "compression_alg": "GZIP",
                "message_payload": json.dumps(assistant),
            },
            {
                "message_id": 20,
                "parent_id": 0,
                "role": "user",
                "message_payload": {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            },
        ],
    }
    view = normalize([{"THREAD_MESSAGES": json.dumps(document)}])
    assert [message.message_id for message in view.messages] == [4, 20]
    assert view.last_message_id == 4
    assert view.status == "IDLE"
    assert view.messages[0].payload["content"][0]["text"] == "done"
    assert view.messages[0].parent_id == 20
