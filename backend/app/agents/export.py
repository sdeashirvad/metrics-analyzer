"""CSV export of rows already read from a thread message."""

from __future__ import annotations

import csv
import io

_FORMULA = ("=", "+", "-", "@")


def csv_document(columns: list[dict], rows: list[list], *, index: int, partial: bool) -> tuple[str, str]:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([_guard(str(column.get("name") or "")) for column in columns])
    for row in rows:
        writer.writerow([_guard("" if cell is None else str(cell)) for cell in row])
    suffix = "-partial" if partial else ""
    return buffer.getvalue(), f"query-{index}{suffix}.csv"


def _guard(value: str) -> str:
    if value.startswith(_FORMULA):
        return "'" + value
    return value
