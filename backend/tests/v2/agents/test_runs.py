from datetime import timedelta

from app.agents.clock import parse_utc
from app.agents.runs import derive_run
from app.agents.thread_view import ThreadMessage

_SUBMITTED = "2026-11-04T00:00:00Z"


def test_assistant_parent_completes_the_matching_run():
    messages = [
        _assistant(100, 1, "decoy from a later id"),
        _assistant(4, 20, "the matching answer"),
    ]
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="data",
        user_message_id="20",
        submitted_at=_SUBMITTED,
        messages=messages,
        thread_status="IDLE",
        now=parse_utc("2026-11-04T00:00:05Z"),
    )
    assert run["status"] == "COMPLETED"
    assert run["message"]["content"]["agentText"] == "the matching answer"
    assert run["message"]["messageId"] == "4"
    assert run["pollAfterMs"] is None
    assert run["error"] is None


def test_unrelated_assistant_leaves_the_run_running():
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="data",
        user_message_id="20",
        submitted_at=_SUBMITTED,
        messages=[_assistant(100, 1, "decoy")],
        thread_status="IN_PROGRESS",
        now=parse_utc(_SUBMITTED) + timedelta(seconds=5),
    )
    assert run["status"] == "RUNNING"
    assert run["message"] is None
    assert run["pollAfterMs"] == 1500
    assert run["overdue"] is False


def test_idle_without_a_child_is_an_execution_error():
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="analysis",
        user_message_id="20",
        submitted_at=_SUBMITTED,
        messages=[],
        thread_status="IDLE",
        now=parse_utc(_SUBMITTED) + timedelta(seconds=5),
    )
    assert run["status"] == "FAILED"
    assert run["error"]["code"] == "AGENT_EXECUTION_ERROR"
    assert run["error"]["retryable"] is True
    assert run["pollAfterMs"] is None


def test_running_past_the_deadline_times_out():
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="analysis",
        user_message_id="20",
        submitted_at=_SUBMITTED,
        messages=[],
        thread_status="IN_PROGRESS",
        now=parse_utc(_SUBMITTED) + timedelta(milliseconds=600000),
    )
    assert run["status"] == "FAILED"
    assert run["error"]["code"] == "AGENT_TIMEOUT"
    assert run["error"]["retryable"] is True


def test_running_at_the_overdue_mark():
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="analysis",
        user_message_id="20",
        submitted_at=_SUBMITTED,
        messages=[],
        thread_status="IN_PROGRESS",
        now=parse_utc(_SUBMITTED) + timedelta(milliseconds=180000),
    )
    assert run["status"] == "RUNNING"
    assert run["overdue"] is True
    assert run["pollAfterMs"] == 5000
    assert [event["type"] for event in run["events"]] == ["submitted", "running", "overdue"]


def test_fresh_accept_is_running():
    submitted = parse_utc(_SUBMITTED)
    run = derive_run(
        run_id="run-token",
        conversation_id="conversation-token",
        agent_key="analysis",
        user_message_id="8",
        submitted_at=_SUBMITTED,
        messages=[],
        thread_status="IN_PROGRESS",
        now=submitted,
    )
    assert run["status"] == "RUNNING"
    assert run["elapsedMs"] == 0
    assert run["pollAfterMs"] == 1500
    assert run["message"] is None
    assert [event["type"] for event in run["events"]] == ["submitted", "running"]


def _assistant(message_id: int, parent_id: int, text: str) -> ThreadMessage:
    return ThreadMessage(
        message_id=message_id,
        parent_id=parent_id,
        role="assistant",
        created_at="2026-11-04T00:00:05Z",
        payload={"role": "assistant", "content": [{"type": "text", "text": text}]},
        agent_name=None,
    )
