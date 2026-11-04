"""Normalised view of one Snowflake thread. Message order is the listed order."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThreadMessage:
    message_id: int
    parent_id: int | None
    role: str
    created_at: str | None
    payload: object
    agent_name: str | None


@dataclass
class ThreadView:
    status: str | None
    last_message_id: int | None
    messages: list[ThreadMessage]
    created_at: str | None
    updated_at: str | None

    @property
    def present(self) -> bool:
        return bool(self.messages) or self.status is not None or self.last_message_id is not None
