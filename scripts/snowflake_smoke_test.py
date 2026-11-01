"""Disposable Snowflake connectivity smoke test. Does not write DQ tables.

Loads connection settings from the untracked backend/.env file.
Prints PASS/FAIL only. Never prints the password.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV_PATH = REPO / "backend" / ".env"
AGENT = "METRICS_ANALYZER.DQ.METRICS_ANALYZER_DQ_AGENT!VERSION$3"
QUESTION = (
    "Which Data Quality controls currently have a Red RAG status? "
    "Return their control IDs and latest status."
)
EXPECTED_RED = ("DQ-001", "DQ-007", "DQ-010", "DQ-020", "DQ-025")
EXPECTED_RAG = {"Amber": 2, "Green": 29, "Red": 5}

SETTING_NAMES = {
    "account": ("SNOWFLAKE_ACCOUNT", "ACCOUNT"),
    "user": ("SNOWFLAKE_USER", "USER"),
    "password": ("SNOWFLAKE_PASSWORD", "PASSWORD"),
    "warehouse": ("SNOWFLAKE_WAREHOUSE", "WAREHOUSE"),
    "database": ("SNOWFLAKE_DATABASE", "DATABASE"),
    "schema": ("SNOWFLAKE_SCHEMA", "SCHEMA"),
    "role": ("SNOWFLAKE_ROLE", "ROLE"),
}


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Environment file not found: {path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def pick(settings: dict[str, str], *names: str) -> str | None:
    lookup = {key.upper(): value for key, value in settings.items()}
    for name in names:
        if name.upper() in lookup and lookup[name.upper()]:
            return lookup[name.upper()]
    return None


def connection_kwargs(settings: dict[str, str]) -> dict[str, str]:
    chosen = {
        field: pick(settings, *names)
        for field, names in SETTING_NAMES.items()
    }
    missing = [field for field in ("account", "user", "password") if not chosen[field]]
    if missing:
        present = ", ".join(sorted(settings))
        raise KeyError(
            "Missing connection settings: "
            + ", ".join(missing)
            + ". Names present in the environment file: "
            + present
        )
    return {field: value for field, value in chosen.items() if value}


def redact(text: str, secret: str | None) -> str:
    if secret:
        text = text.replace(secret, "***")
    return text


def collect_text(node: object, found: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "text" and isinstance(value, str):
                found.append(value)
            else:
                collect_text(value, found)
    elif isinstance(node, list):
        for item in node:
            collect_text(item, found)


def main() -> int:
    try:
        import snowflake.connector
    except ImportError as exc:
        print(f"TEST 1 SQL connection: FAIL ({exc})")
        print("TEST 1 deterministic queries: FAIL (connector not imported)")
        print("TEST 2 Cortex Agent invocation: FAIL (connector not imported)")
        return 1

    password = None
    try:
        settings = load_env(ENV_PATH)
        kwargs = connection_kwargs(settings)
        password = kwargs.get("password")
    except Exception as exc:
        message = redact(str(exc), password)
        print(f"TEST 1 SQL connection: FAIL ({message})")
        print("TEST 1 deterministic queries: FAIL (no connection)")
        print("TEST 2 Cortex Agent invocation: FAIL (no connection)")
        return 1

    connection = None
    sql_connection = "FAIL"
    deterministic = "FAIL"
    agent_result = "FAIL"
    try:
        connection = snowflake.connector.connect(**kwargs)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()"
            )
            user, role, warehouse = cursor.fetchone()
            sql_connection = "PASS"
            print(
                "TEST 1 SQL connection: PASS "
                f"(user={user}, role={role}, warehouse={warehouse})"
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM IDENTIFIER(%(definitions)s)
                """,
                {"definitions": "METRICS_ANALYZER.DQ.DQ_CONTROL_DEFINITIONS"},
            )
            (definition_count,) = cursor.fetchone()
            cursor.execute(
                """
                SELECT RAG_STATUS, COUNT(*)
                FROM IDENTIFIER(%(snapshot)s)
                GROUP BY RAG_STATUS
                """,
                {"snapshot": "METRICS_ANALYZER.DQ.DQ_CONTROL_SNAPSHOT"},
            )
            distribution = {status: count for status, count in cursor.fetchall()}
            count_ok = definition_count == 36
            rag_ok = distribution == EXPECTED_RAG
            deterministic = "PASS" if count_ok and rag_ok else "FAIL"
            print(
                f"TEST 1 deterministic queries: {deterministic} "
                f"(definitions={definition_count}, expected 36; "
                f"rag={distribution}, expected {EXPECTED_RAG})"
            )

            request_body = json.dumps(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": QUESTION}],
                        }
                    ],
                    "stream": False,
                }
            )
            cursor.execute(
                """
                SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
                    %(agent)s,
                    %(request_body)s,
                    TRUE
                )
                """,
                {"agent": AGENT, "request_body": request_body},
            )
            (payload,) = cursor.fetchone()
            if isinstance(payload, str):
                parsed = json.loads(payload)
            else:
                parsed = payload
            texts: list[str] = []
            collect_text(parsed, texts)
            answer = "\n".join(texts)
            present = [control_id for control_id in EXPECTED_RED if control_id in answer]
            missing = [control_id for control_id in EXPECTED_RED if control_id not in answer]
            agent_result = "PASS" if not missing else "FAIL"
            print(f"TEST 2 Cortex Agent invocation: {agent_result}")
            print(f"  expected Red controls found: {present or 'none'}")
            if missing:
                print(f"  missing: {missing}")
            preview = " ".join(answer.split())
            if len(preview) > 500:
                preview = preview[:500] + "..."
            print(f"  answer: {preview or '(no text in response)'}")
    except Exception as exc:
        message = redact(str(exc), password)
        print(f"ERROR: {type(exc).__name__}: {message}")
        if sql_connection == "FAIL":
            print("TEST 1 SQL connection: FAIL")
        if deterministic == "FAIL":
            print("TEST 1 deterministic queries: FAIL")
        if agent_result == "FAIL":
            print("TEST 2 Cortex Agent invocation: FAIL")
        return 1
    finally:
        if connection is not None:
            connection.close()

    return 0 if (sql_connection, deterministic, agent_result) == ("PASS", "PASS", "PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
