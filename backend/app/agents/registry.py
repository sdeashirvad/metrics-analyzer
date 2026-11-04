"""Agent keys the browser may send, and the Snowflake objects they map to."""

from __future__ import annotations

from app.agents.faults import ApiFault

ANALYSIS = "analysis"
DATA = "data"

SNOWFLAKE_AGENTS = {
    ANALYSIS: "METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_COMPLIANCE_V1",
    DATA: "METRICS_ANALYZER.MOCK_DATA.AGENT_APPLICATION_TEXT_TO_SQL_V1",
}

MAX_MESSAGE_CHARS = 2000
MAX_CONTEXT_CHARS = 12000
OVERDUE_AFTER_MS = 180_000
FAIL_AFTER_MS = 600_000
MAX_USER_MESSAGES = 12
MAX_IN_FLIGHT = 4
MAX_ROWS = 1000
ANALYSIS_EVIDENCE_ROWS = 200
MAX_MESSAGE_BYTES = 5_000_000
SOFT_FALLBACK_MS = 45_000

_DISPLAY = {
    ANALYSIS: {
        "displayName": "Analysis & Investigation",
        "description": (
            "Understand what is happening and why. Explore trends, anomalies, "
            "contributing applications and organisational groups, with evidence-backed "
            "explanations and hypotheses."
        ),
        "responseKind": "analysis",
        "returnsDataset": False,
    },
    DATA: {
        "displayName": "Data Explorer",
        "description": (
            "Ask for data in plain language. The Agent generates and runs a read-only "
            "SQL query, then shows you the actual SQL and returned dataset."
        ),
        "responseKind": "dataset",
        "returnsDataset": True,
    },
}


def require_agent_key(agent_key: str) -> str:
    if agent_key not in SNOWFLAKE_AGENTS:
        raise ApiFault(400, "VALIDATION_FAILED", "The agent key is not valid.")
    return agent_key


def snowflake_agent(agent_key: str) -> str:
    require_agent_key(agent_key)
    return SNOWFLAKE_AGENTS[agent_key]


def response_kind(agent_key: str) -> str:
    require_agent_key(agent_key)
    return "dataset" if agent_key == DATA else "analysis"


def agent_matches(name: object, agent_key: str) -> bool:
    if name is None or name == "":
        return True
    if not isinstance(name, str):
        return False
    expected = snowflake_agent(agent_key)
    leaf = expected.rsplit(".", 1)[-1]
    token = name.strip().lower()
    return token in {expected.lower(), leaf.lower(), agent_key}


def is_other_agent(name: object, agent_key: str) -> bool:
    if not isinstance(name, str) or not name.strip():
        return False
    other = DATA if agent_key == ANALYSIS else ANALYSIS
    return agent_matches(name, other) and not agent_matches(name, agent_key)


def public_catalog(status: str) -> dict:
    agents = []
    for key in (ANALYSIS, DATA):
        meta = _DISPLAY[key]
        agents.append(
            {
                "agentKey": key,
                "displayName": meta["displayName"],
                "description": meta["description"],
                "responseKind": meta["responseKind"],
                "status": status,
                "capabilities": {
                    "showsSql": True,
                    "returnsDataset": meta["returnsDataset"],
                    "charts": False,
                    "followUps": True,
                },
                "limits": {
                    "maxMessageChars": MAX_MESSAGE_CHARS,
                    "maxContextChars": MAX_CONTEXT_CHARS,
                    "overdueAfterMs": OVERDUE_AFTER_MS,
                    "failAfterMs": FAIL_AFTER_MS,
                },
            }
        )
    return {"agents": agents}
