from datetime import date, datetime
from decimal import Decimal


def iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def as_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def as_int(value) -> int | None:
    if value is None:
        return None
    return int(value)


def rag(value: str | None) -> str:
    if not value:
        return "insufficient_data"
    lowered = value.strip().lower()
    if lowered in {"green", "amber", "red"}:
        return lowered
    return "insufficient_data"
