"""Short-lived Snowflake connections. Do not share a connection or cursor across requests."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import snowflake.connector
from snowflake.connector.errors import DatabaseError, InterfaceError, OperationalError, ProgrammingError

from app.config import Settings

_READ_SECONDS = 5.0
_deadline: ContextVar[float | None] = ContextVar("dq_read_deadline", default=None)


class ReadTimeout(Exception):
    """The shared deterministic-read deadline was spent."""


def begin_read_deadline(seconds: float = _READ_SECONDS):
    import time

    return _deadline.set(time.monotonic() + seconds)


def end_read_deadline(token) -> None:
    _deadline.reset(token)


def _remaining() -> float | None:
    import time

    deadline = _deadline.get()
    if deadline is None:
        return None
    return deadline - time.monotonic()


def _statement_timeout() -> int | None:
    remaining = _remaining()
    if remaining is None:
        return None
    if remaining <= 0:
        raise ReadTimeout()
    return max(1, math.ceil(remaining))


def _open(settings: Settings, login_timeout: int) -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
        login_timeout=login_timeout,
        request_timeout=300,
        query_timeout=300,
        client_session_keep_alive=False,
        enable_server_session_keep_alive_auto_detection=False,
    )


@contextmanager
def connect(settings: Settings) -> Iterator[snowflake.connector.SnowflakeConnection]:
    connection = _open(settings, 30)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def connect_read(settings: Settings) -> Iterator[snowflake.connector.SnowflakeConnection]:
    """Deterministic reads. login_timeout is only a hint; the monotonic deadline is the budget."""
    hint = _statement_timeout()
    connection = _open(settings, 30 if hint is None else min(30, hint))
    try:
        _statement_timeout()
        yield connection
    finally:
        connection.close()


def dependency_failure(exc: BaseException) -> bool:
    if isinstance(exc, ReadTimeout | OperationalError | InterfaceError):
        return True
    if isinstance(exc, ProgrammingError):
        return _is_timeout(exc)
    if isinstance(exc, DatabaseError):
        return _is_timeout(exc)
    return False


def _is_timeout(exc: BaseException) -> bool:
    text = str(exc).lower()
    code = getattr(exc, "errno", None)
    return code in {604, 630} or "timeout" in text or "canceled" in text or "cancelled" in text


def fetch_all(connection, sql: str, params: dict | None = None) -> list[dict]:
    timeout = _statement_timeout()
    cursor = connection.cursor(snowflake.connector.DictCursor)
    try:
        cursor.execute(sql, params or {}, timeout=timeout)
        rows = cursor.fetchall()
        return list(rows)
    finally:
        cursor.close()


def fetch_one(connection, sql: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(connection, sql, params)
    return rows[0] if rows else None
