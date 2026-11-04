"""Recorded portfolio responses, served only when Snowflake is slow or down.

Files are written offline by `scripts/export_portfolio_snapshots.py` from the same API the UI calls.
Nothing here writes at request time and nothing here talks to Snowflake. There is no second
calculation engine: every stored value is a response the live API produced.

Layout under `fallback_assets/v2/snapshots/`:
- `_index.json`   latest month, the list of recorded scopes and their files.
- `<hash>.json.gz` one pack per scope (month plus filters). A pack maps a request key to a response.

A request is served only when its exact scope has a pack and the pack holds that view. Lists are stored
whole and re-paged with the same paginate function the live service uses. Anything else returns None,
and the caller raises FALLBACK_UNSUPPORTED. A request is never answered from a different month or scope.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import threading
from collections import OrderedDict
from pathlib import Path

_DIR = Path(__file__).resolve().parents[1] / "fallback_assets" / "v2" / "snapshots"
_IGNORED = {"unknown"}
_SCOPE = ("month", "orgTree", "l1", "l2", "legalEntity", "tier", "risk", "lifecycle", "ma")
_SCOPELESS = ("/status", "/filters", "/definitions")
_PAGING = {"page", "pageSize"}
_DEFAULT_ORG_TREE = "BUSINESS_ORG"
_PACK_CACHE = 4

_METRIC_APPS = re.compile(r"^/metrics/[^/]+/applications$")
_BREAKDOWNS = re.compile(r"^/metrics/[^/]+/breakdowns$")

_lock = threading.Lock()
_packs: "OrderedDict[str, dict]" = OrderedDict()


def directory() -> Path:
    return _DIR


def is_list_route(route: str) -> bool:
    return route in {"/metrics", "/applications", "/org/contribution"} or bool(_METRIC_APPS.match(route) or _BREAKDOWNS.match(route))


def default_page_size(route: str) -> int:
    return 50 if route == "/org/contribution" else 25


def split_query(route: str, items: list[tuple[str, str]], latest_month: str | None) -> tuple[str, dict[str, list[str]]]:
    """Return (scope signature, remaining parameters) for a request, in canonical form."""

    scope: dict[str, list[str]] = {}
    rest: dict[str, list[str]] = {}
    scoped = route not in _SCOPELESS
    for name, value in items:
        if value == "" or name in _IGNORED:
            continue
        if scoped and name in _SCOPE:
            if name == "month" and value == latest_month:
                continue
            if name == "orgTree" and value == _DEFAULT_ORG_TREE:
                continue
            scope.setdefault(name, []).append(value)
        elif name in _PAGING and is_list_route(route):
            rest.setdefault(name, []).append(value)
        else:
            rest.setdefault(name, []).append(value)
    signature = "&".join(f"{name}={','.join(sorted(values))}" for name, values in sorted(scope.items()))
    return signature, rest


def request_key(route: str, rest: dict[str, list[str]]) -> str:
    """Key of a view inside a pack. Paging is removed for list routes because lists are stored whole."""

    pairs = sorted(
        (name, value)
        for name, values in rest.items()
        for value in sorted(values)
        if not (is_list_route(route) and name in _PAGING)
        and not (route == "/metrics" and name in {"q", "hasNonCompliant", "rag", "denominatorScope", "sort"})
    )
    query = "&".join(f"{name}={value}" for name, value in pairs)
    return f"{route}?{query}" if query else route


def snapshot_key(route: str, items: list[tuple[str, str]], latest_month: str | None) -> tuple[str, str]:
    signature, rest = split_query(route, items, latest_month)
    return signature, request_key(route, rest)


def pack_name(signature: str) -> str:
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()[:20] + ".json.gz"


def _read_index() -> dict:
    path = _DIR / "_index.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def index() -> dict:
    return _read_index()


def latest_month() -> str | None:
    return index().get("latestMonth")


def available() -> bool:
    return bool(index().get("packs"))


def route_of(path: str) -> str:
    marker = "/portfolio"
    position = path.find(marker)
    return path[position + len(marker):] if position >= 0 else path


def _load_pack(signature: str) -> dict | None:
    entry = index().get("packs", {}).get(signature)
    if not entry:
        return None
    with _lock:
        cached = _packs.get(signature)
        if cached is not None:
            _packs.move_to_end(signature)
            return cached
    path = _DIR / entry["file"]
    if not path.is_file():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return None
    with _lock:
        _packs[signature] = loaded
        while len(_packs) > _PACK_CACHE:
            _packs.popitem(last=False)
    return loaded


def lookup(request) -> dict | None:
    """Return {"data", "asOf", "warnings", "lineage"} for this exact request, or None."""

    if not available():
        return None
    route = route_of(request.url.path)
    items = list(request.query_params.multi_items())
    signature, rest = split_query(route, items, latest_month())
    pack = _load_pack(signature)
    if pack is None:
        return None
    entry = pack.get("entries", {}).get(request_key(route, rest))
    if entry is None:
        return None
    if not entry.get("list"):
        return entry["payload"]
    return _serve_list(route, rest, entry["payload"])


def _serve_list(route: str, rest: dict[str, list[str]], payload: dict) -> dict | None:
    from app.portfolio.support import paginate

    data = payload["data"]
    items = list(data.get("items") or [])
    total = int((data.get("page") or {}).get("totalItems", len(items)))
    complete = len(items) >= total
    if route == "/metrics":
        filtered = _register_filtered(items, rest, data, complete)
        if filtered is None:
            return None
        items, matched = filtered
        complete = True
    elif any(name in rest for name in ("sort", "q", "status", "testStatus", "reason", "denominatorScope", "rag")):
        # Re-sorting or filtering is only exact for views stored with that option.
        return None
    try:
        page = int((rest.get("page") or ["1"])[0])
        size = int((rest.get("pageSize") or [str(default_page_size(route))])[0])
    except ValueError:
        return None
    if page < 1 or size < 1 or size > 100:
        return None
    if not complete and page * size > len(items):
        return None
    window, block = paginate(items, page, size)
    shaped = dict(data)
    shaped["items"] = window
    shaped["page"] = block if complete else {**block, "totalItems": total, "totalPages": -(-total // size)}
    if route == "/metrics":
        shaped["totals"] = _register_totals(data, rest, matched)
    return {**payload, "data": shaped}


def _register_filtered(items: list, rest: dict[str, list[str]], data: dict, complete: bool):
    """Return (items after filters and sort, number matched by q and denominatorScope) or None."""

    from app.portfolio.definitions import RAG_VALUES
    from app.portfolio.scope import METRIC_SORT, parse_sort
    from app.portfolio.services.metrics import _sort_register

    if not complete:
        return None
    query = (rest.get("q") or [""])[0].strip()
    wanted_rag = set(rest.get("rag") or [])
    wanted_scope = set(rest.get("denominatorScope") or [])
    if wanted_rag - set(RAG_VALUES):
        return None
    totals = data.get("totals") or {}
    if (query or wanted_scope) and totals.get("metrics") != totals.get("metricsWithRowsInMonth"):
        return None
    chosen = []
    for item in items:
        if query and query.upper() not in item["metricId"].upper():
            continue
        if wanted_scope and item["denominatorScope"] not in wanted_scope:
            continue
        chosen.append(item)
    matched = len(chosen)
    if (rest.get("hasNonCompliant") or ["false"])[0] == "true":
        chosen = [item for item in chosen if int(item["nonCompliantApplications"] or 0) > 0]
    if wanted_rag:
        chosen = [item for item in chosen if item["rag"] in wanted_rag]
    try:
        field, direction = parse_sort((rest.get("sort") or [None])[0], METRIC_SORT, ("applications", "desc"))
    except Exception:  # noqa: BLE001 - an invalid sort is the live service's error to report
        return None
    return _sort_register(chosen, field, direction), matched


def _register_totals(data: dict, rest: dict[str, list[str]], matched: int) -> dict:
    totals = dict(data.get("totals") or {})
    if (rest.get("q") or [""])[0].strip() or rest.get("denominatorScope"):
        totals = {"metrics": matched, "metricsWithRowsInMonth": matched}
    return totals


def scopes() -> dict:
    return index().get("packs", {})


def reset() -> None:
    with _lock:
        _packs.clear()

