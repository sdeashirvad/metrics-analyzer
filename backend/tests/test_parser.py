import json
from pathlib import Path

from app.cortex.response_parser import parse_final_answer


def test_parser_reads_captured_agent_message():
    payload = json.loads(Path("tests/fixtures/agent_response.json").read_text(encoding="utf-8"))
    answer, thread_id = parse_final_answer(payload)
    assert thread_id == "thread-captured"
    for control_id in ("DQ-001", "DQ-007", "DQ-010", "DQ-020", "DQ-025"):
        assert control_id in answer
    assert "DQ-999" not in answer
    assert "planning" not in answer


def test_parser_keeps_last_assistant_text_only():
    payload = {
        "thread_id": "thread-1",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Which controls are red?"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "text": "tool trace DQ-999"},
                    {"type": "thinking", "text": "planning text"},
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_result", "text": "rows"},
                    {"type": "text", "text": "Red controls: DQ-001, DQ-007, DQ-010, DQ-020, DQ-025."},
                ],
            },
        ],
    }
    answer, thread_id = parse_final_answer(payload)
    assert thread_id == "thread-1"
    assert "DQ-001" in answer
    assert "DQ-999" not in answer
    assert "planning" not in answer
    assert "tool trace" not in answer
