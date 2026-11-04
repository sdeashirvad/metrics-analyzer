"""Agent capacity published by the agents package and read by the dashboard."""

_reader = None


def bind(reader) -> None:
    global _reader
    _reader = reader


def current() -> str:
    if _reader is None:
        return "unavailable"
    status = _reader()
    if status not in {"available", "busy", "unavailable"}:
        return "unavailable"
    return status
