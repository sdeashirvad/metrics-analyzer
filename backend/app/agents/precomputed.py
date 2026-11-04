"""Static investigation narratives.

No packaged file is served. Callers show no static narrative.
"""

from __future__ import annotations

from app.agents.registry import SOFT_FALLBACK_MS

__all__ = ["SOFT_FALLBACK_MS", "get_precomputed"]


def get_precomputed(kind: str, target_id: str, month: str) -> None:
    """Return no precomputed analysis for this target."""
    del kind, target_id, month
    return None
