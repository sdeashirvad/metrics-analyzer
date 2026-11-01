"""Keep only the last assistant message's text items. Drop tool traces and planning text."""

from __future__ import annotations

import json


def parse_final_answer(payload) -> tuple[str, str | None]:
    document = payload
    if isinstance(document, str):
        document = json.loads(document)
    if not isinstance(document, dict):
        raise ValueError("Agent response was not a JSON object")
    thread_id = _thread_id(document)
    message = _last_assistant(document)
    if message is None:
        raise ValueError("Agent response has no assistant message")
    parts = []
    for item in message.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    answer = "\n".join(part.strip() for part in parts if part.strip())
    if not answer:
        raise ValueError("Agent response assistant message has no text content")
    return answer, thread_id


def _thread_id(document: dict) -> str | None:
    for key in ("thread_id", "threadId", "cortex_thread_id"):
        value = document.get(key)
        if isinstance(value, str) and value:
            return value
    metadata = document.get("metadata")
    if isinstance(metadata, dict):
        for key in ("thread_id", "threadId"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _last_assistant(document: dict) -> dict | None:
    if str(document.get("role", "")).lower() == "assistant" and isinstance(document.get("content"), list):
        return document
    messages = _messages(document)
    for message in reversed(messages):
        if isinstance(message, dict) and str(message.get("role", "")).lower() == "assistant":
            return message
    return None


def _messages(document: dict) -> list:
    if isinstance(document.get("messages"), list):
        return document["messages"]
    for key in ("response", "output", "result", "data"):
        nested = document.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("messages"), list):
            return nested["messages"]
        if isinstance(nested, str):
            try:
                parsed = json.loads(nested)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("messages"), list):
                return parsed["messages"]
    return []
