"""One proven Cortex call. The third argument stays TRUE because that call passed."""

from __future__ import annotations

import json
import logging
import threading

from app.config import Settings
from app.cortex.response_parser import parse_final_answer
from app.db.connection import fetch_one

logger = logging.getLogger(__name__)
_AGENT_SLOTS = threading.Semaphore(2)


def run_agent(connection, settings: Settings, prompt: str) -> str:
    payload = execute_agent(connection, settings, prompt)
    answer, thread_id = parse_final_answer(payload)
    logger.info("cortex agent completed thread_id=%s", thread_id or "none")
    return answer


def execute_agent(connection, settings: Settings, prompt: str):
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "stream": False,
        }
    )
    acquired = _AGENT_SLOTS.acquire(timeout=180)
    if not acquired:
        raise TimeoutError("Cortex agent slots are busy")
    try:
        row = fetch_one(
            connection,
            "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(%(agent)s, %(request_body)s, TRUE) AS AGENT_RESPONSE",
            {"agent": settings.cortex_agent, "request_body": body},
        )
    finally:
        _AGENT_SLOTS.release()
    if not row:
        raise RuntimeError("Cortex agent returned no row")
    return row.get("AGENT_RESPONSE")
