"""Resolve the reporting month. An explicit month wins. Otherwise the latest month in the view."""

from __future__ import annotations

from datetime import date, timedelta

from app.common.v2_errors import unavailable
from app.portfolio.repository import latest_reporting_month


def resolve_month(explicit, connection=None, *, known_latest=None):
    """Return (month, month_source). month_source is selected or latest_available."""
    if explicit is not None and str(explicit).strip() != "":
        return str(explicit).strip(), "selected"
    if known_latest:
        return known_latest, "latest_available"
    close = None
    if connection is None:
        from app.config import load_settings
        from app.db.connection import connect

        ctx = connect(load_settings())
        connection = ctx.__enter__()
        close = ctx
    try:
        latest = latest_reporting_month(connection)
    finally:
        if close is not None:
            close.__exit__(None, None, None)
    if not latest:
        raise unavailable("No reporting month is available.")
    return latest, "latest_available"


def previous_calendar_month(month: str) -> str:
    year, mon, _day = (int(part) for part in month.split("-"))
    if mon == 1:
        year -= 1
        mon = 12
    else:
        mon -= 1
    if mon == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, mon + 1, 1)
    return (next_first - timedelta(days=1)).isoformat()


def prior_in_index(month: str, months: list[str]) -> str | None:
    prior = previous_calendar_month(month)
    if prior in months:
        return prior
    return None
