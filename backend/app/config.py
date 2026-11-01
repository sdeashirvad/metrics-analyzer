"""Runtime settings. Credentials come from the environment or backend/.env. Never log them."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_ROOT / ".env"

AGENT_IDENTITY = "metrics-analyzer-dq-agent-v3"
DEFAULT_AGENT = "METRICS_ANALYZER.DQ.METRICS_ANALYZER_DQ_AGENT!VERSION$3"
CALCULATION_VERSION = "dq-rag-v1"
SUMMARY_PROMPT = "summary-v1"
INVESTIGATION_PROMPT = "investigation-v1"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _pick(settings: dict[str, str], *names: str) -> str | None:
    lookup = {key.upper(): value for key, value in settings.items()}
    for name in names:
        found = lookup.get(name.upper())
        if found:
            return found
    return None


class Settings(BaseModel):
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_database: str = "METRICS_ANALYZER"
    snowflake_schema: str = "DQ"
    snowflake_role: str = "ACCOUNTADMIN"
    cortex_agent: str = DEFAULT_AGENT
    model_identity: str = AGENT_IDENTITY
    calculation_version: str = CALCULATION_VERSION
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    def qualified(self, table: str) -> str:
        for part in (self.snowflake_database, self.snowflake_schema, table):
            if not part.replace("_", "").isalnum():
                raise ValueError("Unsafe Snowflake identifier")
        return f"{self.snowflake_database}.{self.snowflake_schema}.{table}"


def load_settings() -> Settings:
    raw = _parse_env_file(ENV_PATH)
    raw.update(os.environ)
    account = _pick(raw, "SNOWFLAKE_ACCOUNT", "ACCOUNT")
    user = _pick(raw, "SNOWFLAKE_USER", "USER")
    password = _pick(raw, "SNOWFLAKE_PASSWORD", "PASSWORD")
    missing = [
        name
        for name, value in (("account", account), ("user", user), ("password", password))
        if not value
    ]
    if missing:
        raise RuntimeError("Missing Snowflake settings: " + ", ".join(missing))
    origins = _pick(raw, "CORS_ORIGINS")
    return Settings(
        snowflake_account=account or "",
        snowflake_user=user or "",
        snowflake_password=password or "",
        snowflake_warehouse=_pick(raw, "SNOWFLAKE_WAREHOUSE", "WAREHOUSE") or "COMPUTE_WH",
        snowflake_database=_pick(raw, "SNOWFLAKE_DATABASE", "DATABASE") or "METRICS_ANALYZER",
        snowflake_schema=_pick(raw, "SNOWFLAKE_SCHEMA", "SCHEMA") or "DQ",
        snowflake_role=_pick(raw, "SNOWFLAKE_ROLE", "ROLE") or "ACCOUNTADMIN",
        cortex_agent=_pick(raw, "CORTEX_AGENT") or DEFAULT_AGENT,
        cors_origins=[item.strip() for item in origins.split(",")] if origins else [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )
