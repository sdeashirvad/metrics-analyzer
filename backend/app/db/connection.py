"""Short-lived Snowflake connections. Do not share a connection or cursor across requests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import snowflake.connector

from app.config import Settings


@contextmanager
def connect(settings: Settings) -> Iterator[snowflake.connector.SnowflakeConnection]:
    connection = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
        login_timeout=30,
        request_timeout=300,
        query_timeout=300,
        client_session_keep_alive=False,
        enable_server_session_keep_alive_auto_detection=False,
    )
    try:
        yield connection
    finally:
        connection.close()


def fetch_all(connection, sql: str, params: dict | None = None) -> list[dict]:
    cursor = connection.cursor(snowflake.connector.DictCursor)
    try:
        cursor.execute(sql, params or {})
        rows = cursor.fetchall()
        return list(rows)
    finally:
        cursor.close()


def fetch_one(connection, sql: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(connection, sql, params)
    return rows[0] if rows else None
