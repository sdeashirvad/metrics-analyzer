import json
from pathlib import Path

from app.agents.parse import parse_assistant

_FIXTURE = Path(__file__).parent / "fixtures" / "message_payload.json"


def test_parser_keeps_sql_tool_rows_and_ignores_prose_table():
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    parsed = parse_assistant(payload, kind="dataset")
    dumped = json.dumps(parsed)
    assert "secret plan" not in dumped
    assert "999" in parsed["agentText"]
    assert parsed["interpretedIntent"] == "Count reporting applications."
    assert parsed["assumptions"] == ["One row per application."]
    assert len(parsed["queries"]) == 1
    query = parsed["queries"][0]
    assert query["toolName"] == "system_execute_sql"
    assert query["sql"].startswith("SELECT COUNT")
    assert "SHOULD_NOT_USE" not in query["sql"]
    assert query["queryId"] == "01c82c6e-0002-f949-000f-4bee0004c0d6"
    assert query["rows"] == [["923", ""]]
    assert "999" not in json.dumps(query["rows"])
    assert query["rowCount"] == 1
    assert query["columns"][0]["name"] == "APPLICATIONS_REPORTING"
    assert query["columns"][0]["nullable"] is False
    assert query["columns"][1]["name"] == "TEST_RESULT"
    assert query["columns"][1]["nullable"] is True
    assert parsed["primaryQueryIndex"] == 0


def test_parser_reads_compressed_message_payload_as_json():
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    row = {
        "is_compressed": True,
        "compression_alg": "GZIP",
        "message_payload": json.dumps(payload),
    }
    parsed = parse_assistant(row, kind="dataset")
    assert parsed["queries"][0]["rows"] == [["923", ""]]
    assert "secret plan" not in json.dumps(parsed)


def test_parser_reads_metadata_beside_the_result_set():
    payload = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "One row."},
            {
                "type": "tool_use",
                "tool_use": {"tool_use_id": "tu-2", "name": "system_execute_sql"},
            },
            {
                "type": "tool_result",
                "tool_result": {
                    "tool_use_id": "tu-2",
                    "status": "success",
                    "content": [
                        {
                            "type": "json",
                            "json": {
                                "sql": "SELECT 1 AS N",
                                "query_id": "qid-meta",
                                "result_set": {"data": [["1"]]},
                                "resultSetMetaData": {
                                    "numRows": 1,
                                    "rowType": [
                                        {"name": "N", "type": "fixed", "nullable": False, "scale": 0}
                                    ],
                                },
                            },
                        }
                    ],
                },
            },
        ],
    }
    parsed = parse_assistant(payload, kind="dataset")
    query = parsed["queries"][0]
    assert query["rowCount"] == 1
    assert query["columns"][0]["name"] == "N"
    assert query["rows"] == [["1"]]


def test_parser_keeps_prose_and_sql_and_hides_tool_payloads():
    payload = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Twenty applications are non-compliant."},
            {"type": "note", "text": "The cluster is in one division."},
            {"type": "diagnostic", "content": {"tool_use_id": "hidden", "sql": "SELECT SECRET"}},
            {"type": "diagnostic", "text": '{"sql": "SELECT SECRET"}'},
            {
                "type": "tool_use",
                "tool_use": {"tool_use_id": "tu-mix", "name": "system_execute_sql"},
            },
            {
                "type": "tool_result",
                "tool_result": {
                    "tool_use_id": "tu-mix",
                    "status": "success",
                    "content": [
                        {
                            "type": "json",
                            "json": {
                                "sql": "SELECT 20 AS N",
                                "result_set": {"data": [["20"]]},
                                "resultSetMetaData": {
                                    "numRows": 1,
                                    "rowType": [{"name": "N", "type": "fixed", "nullable": False, "scale": 0}],
                                },
                            },
                        }
                    ],
                },
            },
        ],
    }
    parsed = parse_assistant(payload, kind="dataset")
    dumped = json.dumps(parsed)
    assert "Twenty applications" in parsed["agentText"]
    assert "one division" in parsed["agentText"]
    assert "SECRET" not in dumped
    assert parsed["queries"][0]["sql"] == "SELECT 20 AS N"
    assert parsed["queries"][0]["rows"] == [["20"]]
    assert not any(item["code"] == "UNKNOWN_BLOCK_TYPE" for item in parsed["warnings"])


def test_parser_caps_rows():
    wide = _rows_payload(1001)
    dataset = parse_assistant(wide, kind="dataset")
    assert dataset["queries"][0]["rowsReturned"] == 1000
    assert dataset["queries"][0]["truncation"]["reason"] == "RESPONSE_CAP"

    analysis = parse_assistant(_rows_payload(201), kind="analysis")
    assert analysis["evidence"][0]["rowsReturned"] == 200
    assert analysis["evidence"][0]["truncation"]["reason"] == "RESPONSE_CAP"


def _rows_payload(count: int) -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Rows."},
            {
                "type": "tool_result",
                "tool_result": {
                    "tool_use_id": "tu-cap",
                    "status": "success",
                    "content": [
                        {
                            "type": "json",
                            "json": {
                                "sql": "SELECT N",
                                "result_set": {"data": [[str(index)] for index in range(count)]},
                                "resultSetMetaData": {
                                    "numRows": count,
                                    "rowType": [{"name": "N", "type": "fixed", "nullable": False, "scale": 0}],
                                },
                            },
                        }
                    ],
                },
            },
        ],
    }
