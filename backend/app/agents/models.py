"""Request bodies for the agent routes. Unknown fields are rejected."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntrySurface = Literal[
    "general",
    "dashboard",
    "register_preview",
    "metric_summary",
    "metric_investigation",
    "application_investigation",
]


class FiltersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = None
    orgTree: Literal["BUSINESS_ORG", "BU"] | None = None
    l1: list[str] | None = None
    l2: list[str] | None = None
    legalEntity: list[str] | None = None
    tier: list[int] | None = None
    risk: list[str] | None = None
    lifecycle: list[str] | None = None
    ma: Literal["Y", "N"] | None = None


class ScopeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = None
    metricId: str | None = None
    eonId: str | None = None
    filters: FiltersIn | None = None


class ItemsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] | None = None
    exclude: list[str] | None = None


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrySurface: EntrySurface
    scope: ScopeIn = Field(default_factory=ScopeIn)
    items: ItemsIn | None = None


class CreateConversationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agentKey: Literal["analysis", "data"]
    message: str
    context: ContextRequest
    contextHash: str
    clientRequestId: str


class SendMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    clientRequestId: str
