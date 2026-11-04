"""Record the portfolio responses the UI needs, so the app can run without Snowflake.

Run while the API is healthy:

    python scripts/export_portfolio_snapshots.py --base http://127.0.0.1:8080 [--threads 8]
    python scripts/export_portfolio_snapshots.py --only months          # the 12 months at default scope
    python scripts/export_portfolio_snapshots.py --only single          # single-value filters, latest month
    python scripts/export_portfolio_snapshots.py --only default         # the latest month, default scope
    python scripts/export_portfolio_snapshots.py --scope "tier=4"       # one scope (repeatable)
    python scripts/export_portfolio_snapshots.py --force                # re-record scopes already packed

It only reads the API, so every stored value is a response the live code produced. It never computes
a value. Each scope becomes one gzip pack under app/fallback_assets/v2/snapshots/, and _index.json
lists them. A scope that already has a pack is skipped unless --force is given, so an interrupted
run resumes. Coverage (what a pack holds) is printed at the end and saved in the index.

Coverage per scope, matching what the UI requests outside the Agent workspace:
  Dashboard      overview, trends, compliance, testing(series), risk, tier, lifecycle, rto, legalEntity,
                 org contribution levels 1 and 2, attention lists (six values)
  Register       the whole metric list, plus each metric preview
  Summary        each metric summary, trend, and every breakdown dimension
  Investigation  each metric investigation and its affected applications
  Application investigation (default scope only): the dashboard attention list, plus the first page of
                 each metric's applications in the latest month
Global: status, filters, definitions, and data coverage per month.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.portfolio import snapshots  # noqa: E402

BREAKDOWNS = ["legalEntity", "tier", "risk", "lifecycle", "complianceReason", "testStatus"]
DISTRIBUTIONS = ["risk", "tier", "lifecycle", "rto", "legalEntity"]
ATTENTION = ["nonCompliant", "noCompletedTest", "failedTest", "newlyNonCompliant", "resolved", "persistentNonCompliant"]
FIRST_APPS_PER_METRIC = 15
DASHBOARD_APPS = 25

_write_lock = threading.Lock()


class Recorder:
    """Collects the responses of one scope, then merges them into the packs on disk."""

    def __init__(self, base: str, latest: str) -> None:
        self.base = base
        self.latest = latest
        self.entries: dict[str, dict[str, dict]] = {}
        self.skipped: list[str] = []
        self._lock = threading.Lock()
        self.requests = 0

    def fetch(self, route: str, query: list[tuple[str, str]]):
        url = f"{self.base}/api/v1/portfolio{route}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        last = "error"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=90) as response:
                    with self._lock:
                        self.requests += 1
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                if exc.code < 500:
                    break
            except Exception as exc:  # noqa: BLE001
                last = type(exc).__name__
            time.sleep(1 + attempt)
        with self._lock:
            self.skipped.append(f"{route}?{urllib.parse.urlencode(query)} {last}")
        return None

    def put(self, route: str, query: list[tuple[str, str]], body: dict, *, list_items: list | None = None):
        meta = body["meta"]
        if meta.get("source") != "snowflake":
            raise RuntimeError(f"{route} was not answered live; stop and retry when the API is healthy")
        signature, key = snapshots.snapshot_key(route, query, self.latest)
        data = body["data"]
        if list_items is not None:
            data = {**data, "items": list_items}
        payload = {
            "data": data,
            "asOf": meta.get("asOf"),
            "warnings": [w for w in meta.get("warnings", []) if w.get("code") != "PACKAGED_DATA"],
            "lineage": meta.get("lineage"),
        }
        with self._lock:
            self.entries.setdefault(signature, {})[key] = {"list": list_items is not None, "payload": payload}

    def record(self, route: str, query: list[tuple[str, str]]):
        body = self.fetch(route, query)
        if body is None:
            return None
        self.put(route, query, body)
        return body["data"]

    def record_list(self, route: str, query: list[tuple[str, str]], max_pages: int = 10):
        """Store a whole list: page after page at the largest page size, in the service's own order."""

        items: list = []
        first = None
        page = 1
        while True:
            body = self.fetch(route, [*query, ("page", str(page)), ("pageSize", "100")])
            if body is None:
                return None
            first = first or body
            items.extend(body["data"].get("items", []))
            block = body["data"].get("page") or {}
            if page >= int(block.get("totalPages") or 1) or page >= max_pages:
                break
            page += 1
        self.put(route, query, first, list_items=items)
        return items


def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def scope_items(scope: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(scope)


def record_scope(rec: Recorder, scope: list[tuple[str, str]], pool: ThreadPoolExecutor, *, applications: str) -> None:
    """applications: 'none', 'dashboard' (attention list only) or 'full' (attention list plus per-metric first pages)."""

    q = scope_items(scope)
    no_month = [(n, v) for n, v in q if n != "month"]
    no_org_level = [(n, v) for n, v in q if n not in {"l1", "l2"}]
    tasks = [
        ("/overview", q),
        ("/trends", no_month),
        ("/distributions/compliance", q),
        ("/distributions/testing", [*q, ("series", "true")]),
        *[(f"/distributions/{name}", q) for name in DISTRIBUTIONS],
    ]
    list(pool.map(lambda task: rec.record(*task), tasks))
    for level in ("1", "2"):
        rec.record_list("/org/contribution", [*no_org_level, ("level", level)])
    attention_items: dict[str, list] = {}
    for item in ATTENTION:
        found = rec.record_list("/applications", [*q, ("attention", item)], max_pages=2 if applications != "none" else 1)
        attention_items[item] = found or []

    register = rec.record_list("/metrics", q)
    metrics = [item["metricId"] for item in (register or [])]

    def per_metric(metric: str):
        base = f"/metrics/{quote(metric)}"
        rec.record(f"{base}/preview", q)
        rec.record(base, q)
        rec.record(f"{base}/trend", no_month)
        rec.record_list(f"{base}/breakdowns", [*q, ("dimension", "org"), ("level", "1")])
        rec.record_list(f"{base}/breakdowns", [*q, ("dimension", "org"), ("level", "2")])
        for dim in BREAKDOWNS:
            rec.record_list(f"{base}/breakdowns", [*q, ("dimension", dim)])
        apps = rec.record_list(f"{base}/applications", q)
        rec.record(f"/investigations/metrics/{quote(metric)}", q)
        return metric, apps or []

    results = list(pool.map(per_metric, metrics))

    if applications == "none":
        return
    month_query = [(n, v) for n, v in q if n == "month"]
    seen: set[tuple[str, str | None]] = set()
    wanted: list[tuple[str, str | None]] = []
    for item in (attention_items.get("nonCompliant") or [])[:DASHBOARD_APPS]:
        wanted.append((item["eonId"], None))
    if applications == "full":
        for metric, apps in results:
            for row in apps[:FIRST_APPS_PER_METRIC]:
                wanted.append((row["eonId"], metric))
    unique = [pair for pair in wanted if not (pair in seen or seen.add(pair))]

    def investigate(pair):
        eon, metric = pair
        query = [*month_query, *([("metricId", metric)] if metric else [])]
        rec.record(f"/investigations/applications/{quote(eon)}", query)

    list(pool.map(investigate, unique))


def merge_into_packs(rec: Recorder, scope_label: str, note: dict) -> None:
    directory = snapshots.directory()
    directory.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        index_path = directory / "_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
        index.setdefault("packs", {})
        for signature, entries in rec.entries.items():
            file = snapshots.pack_name(signature)
            target = directory / file
            existing: dict = {}
            if target.is_file():
                with gzip.open(target, "rt", encoding="utf-8") as handle:
                    existing = json.load(handle).get("entries", {})
            existing.update(entries)
            temporary = target.with_suffix(".tmp")
            with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as handle:
                json.dump({"signature": signature, "entries": existing}, handle, separators=(",", ":"))
            temporary.replace(target)
            index["packs"][signature] = {
                "file": file,
                "entries": len(existing),
                "bytes": target.stat().st_size,
                "label": signature or "default scope, latest month",
            }
        index["latestMonth"] = rec.latest
        index.setdefault("exported", {})[scope_label] = note
        index["count"] = sum(item["entries"] for item in index["packs"].values())
        index_path.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")


def plan(filters: dict, latest: str) -> list[tuple[str, list[tuple[str, str]], str]]:
    """(label, scope query, applications mode) for each scope to record."""

    scopes: list[tuple[str, list[tuple[str, str]], str]] = []
    scopes.append(("default", [], "full"))
    months = [item["month"] for item in filters["months"] if item["month"] != latest]
    for month in months:
        scopes.append((f"month={month}", [("month", month)], "dashboard"))
    for tier in filters["tiers"]:
        scopes.append((f"tier={tier}", [("tier", str(tier))], "none"))
    for risk in filters["risks"]:
        scopes.append((f"risk={risk}", [("risk", risk)], "none"))
    for item in filters["lifecycles"]:
        scopes.append((f"lifecycle={item}", [("lifecycle", item)], "none"))
    for item in filters["maOptions"]:
        scopes.append((f"ma={item}", [("ma", item)], "none"))
    scopes.append(("orgTree=BU", [("orgTree", "BU")], "none"))
    for item in filters["orgTrees"]["BUSINESS_ORG"]["level1"]:
        scopes.append((f"l1={item['value']}", [("l1", item["value"])], "none"))
    for item in filters["orgTrees"]["BU"]["level1"]:
        scopes.append((f"BU l1={item['value']}", [("orgTree", "BU"), ("l1", item["value"])], "none"))
    for item in filters["legalEntities"]:
        scopes.append((f"legalEntity={item['code']}", [("legalEntity", item["code"])], "none"))
    return scopes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--only", choices=["default", "months", "single", "all"], default="all")
    parser.add_argument("--scope", action="append", default=[], help='exact scope label, for example "tier=4"; repeatable')
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    probe = Recorder(args.base, "")
    status = probe.fetch("/status", [])
    if not status or status["meta"]["source"] != "snowflake":
        print("The API must be answering from Snowflake to record snapshots.")
        return 1
    latest = status["data"]["latestMonth"]
    probe.latest = latest
    filters_body = probe.fetch("/filters", [])
    definitions_body = probe.fetch("/definitions", [])
    if not filters_body or not definitions_body:
        print("Could not read the filter catalogue or definitions.")
        return 1
    probe.put("/status", [], status)
    probe.put("/filters", [], filters_body)
    probe.put("/definitions", [], definitions_body)
    merge_into_packs(probe, "global", {"requests": probe.requests})

    planned = plan(filters_body["data"], latest)
    if args.scope:
        planned = [item for item in planned if item[0] in set(args.scope)]
    elif args.only == "default":
        planned = [item for item in planned if item[0] == "default"]
    elif args.only == "months":
        planned = [item for item in planned if item[0] == "default" or item[0].startswith("month=")]
    elif args.only == "single":
        planned = [item for item in planned if item[0] != "default" and not item[0].startswith("month=")]

    directory = snapshots.directory()
    existing_index = {}
    if (directory / "_index.json").is_file():
        existing_index = json.loads((directory / "_index.json").read_text(encoding="utf-8"))
    done = set(existing_index.get("exported", {}))
    failures: list[str] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, min(16, args.threads))) as pool:
        for label, scope, applications in planned:
            if label in done and not args.force:
                print(f"skip {label} (already recorded)")
                continue
            rec = Recorder(args.base, latest)
            began = time.time()
            if label == "default" or label.startswith("month="):
                month = scope[0][1] if scope else latest
                body = rec.fetch("/data-coverage", [("month", month)] if scope else [])
                if body:
                    rec.put("/data-coverage", [("month", month)] if scope else [], body)
            try:
                record_scope(rec, scope, pool, applications=applications)
            except RuntimeError as exc:
                print(f"stop at {label}: {exc}")
                return 2
            note = {
                "requests": rec.requests,
                "entries": sum(len(v) for v in rec.entries.values()),
                "skipped": rec.skipped[:20],
                "skippedCount": len(rec.skipped),
                "seconds": round(time.time() - began, 1),
                "recordedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            merge_into_packs(rec, label, note)
            if rec.skipped:
                failures.append(f"{label}: {len(rec.skipped)} skipped")
            print(f"recorded {label}: {note['entries']} views, {rec.requests} requests, {note['seconds']}s, skipped {len(rec.skipped)}")
    print(f"finished in {round(time.time() - started)}s; scopes with skipped views: {failures or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
