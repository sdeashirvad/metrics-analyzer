"""Read one packaged JSON file. Paths come from a fixed map, never from the request."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "fallback_assets"

FILES = {
    "manifest": "manifest.json",
    "dq-definitions": "dq/definitions.json",
    "dq-portfolio": "dq/summary.json",
    "dq-results": "dq/results.json",
    "dq-desks": "dq/results-by-desk.json",
    "dq-exceptions": "dq/exceptions.json",
    "dq-events": "dq/events.json",
    "dq-commentary": "dq/commentary.json",
    "dq-hierarchy": "dq/hierarchy.json",
    "tr-overview": "tr/overview.json",
    "tr-register": "tr/register.json",
    "tr-investigations": "tr/investigations.json",
}


def read_json(key: str):
    relative = FILES.get(key)
    if relative is None or ".." in relative:
        raise KeyError(key)
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(key)
    return json.loads(path.read_text(encoding="utf-8"))


def read_metric(kind: str, metric_id: str):
    if kind not in {"metrics", "trends", "org", "investigation"}:
        raise KeyError(kind)
    if not metric_id.startswith("M") or not metric_id[1:].isdigit():
        raise KeyError(metric_id)
    path = ROOT / "tr" / kind / f"{metric_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
