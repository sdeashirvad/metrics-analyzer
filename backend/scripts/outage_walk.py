"""Walk every recorded view against an API process whose Snowflake account is unreachable.

Start the API for this test with an unreachable account in THAT process only, for example
    SNOWFLAKE_ACCOUNT=outage-simulation-unreachable.invalid uvicorn app.main:app --port 8082
then run
    python scripts/outage_walk.py --base http://127.0.0.1:8082 --out report.json

For each recorded scope pack it requests every stored view through the real HTTP stack and checks that
the response is 200, says `source: packaged`, and carries exactly the data that was recorded. It also
probes combinations that were never recorded and expects an explicit FALLBACK_UNSUPPORTED, and checks
how the Agent endpoints behave while Snowflake is down. Nothing is written to the repository assets.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "app" / "fallback_assets" / "v2" / "snapshots"


def url_for(base: str, signature: str, key: str) -> str:
    route, _, query = key.partition("?")
    parts = [part for part in (query, signature) if part]
    suffix = "&".join(parts)
    path = quote(route, safe="/:,")
    return f"{base}/api/v1/portfolio{path}" + (f"?{suffix}" if suffix else "")


def check(client: httpx.Client, base: str, signature: str, key: str, entry: dict) -> dict:
    url = url_for(base, signature, key)
    started = time.perf_counter()
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return {"url": url, "ok": False, "why": f"transport {type(exc).__name__}"}
    elapsed = round((time.perf_counter() - started) * 1000)
    result = {"url": url, "status": response.status_code, "ms": elapsed, "ok": False}
    if response.status_code != 200:
        result["why"] = response.text[:160]
        return result
    body = response.json()
    if body.get("meta", {}).get("source") != "packaged":
        result["why"] = f"source={body.get('meta', {}).get('source')}"
        return result
    data, recorded = body["data"], entry["payload"]["data"]
    if entry.get("list"):
        # Lists are stored whole and re-paged; compare identity, not the page window.
        if (data.get("page") or {}).get("totalItems") != (recorded.get("page") or {}).get("totalItems"):
            result["why"] = "totalItems differs"
            return result
        window = data.get("items") or []
        if window != (recorded.get("items") or [])[: len(window)]:
            result["why"] = "items differ from the recorded list"
            return result
    elif data != recorded:
        result["why"] = "data differs from the recorded response"
        return result
    result["ok"] = True
    return result


def walk(base: str, threads: int, limit: int | None) -> dict:
    index = json.loads((SNAP / "_index.json").read_text("utf-8"))
    jobs: list[tuple[str, str, dict]] = []
    for signature, pack in index["packs"].items():
        with gzip.open(SNAP / pack["file"], "rt", encoding="utf-8") as handle:
            entries = json.load(handle)["entries"]
        keys = list(entries)[:limit] if limit else list(entries)
        jobs.extend((signature, key, entries[key]) for key in keys)
    failures: list[dict] = []
    latencies: list[int] = []
    per_scope: dict[str, list[int]] = {}
    with httpx.Client(timeout=30) as client, ThreadPoolExecutor(max_workers=threads) as pool:
        for (signature, _key, _entry), outcome in zip(jobs, pool.map(lambda job: check(client, base, *job), jobs)):
            scope = per_scope.setdefault(signature or "default", [0, 0])
            scope[0] += 1
            if outcome["ok"]:
                scope[1] += 1
                latencies.append(outcome["ms"])
            else:
                failures.append(outcome)
    latencies.sort()
    return {
        "requests": len(jobs),
        "ok": len(jobs) - len(failures),
        "failures": failures[:25],
        "failureCount": len(failures),
        "p50Ms": latencies[len(latencies) // 2] if latencies else None,
        "p95Ms": latencies[int(len(latencies) * 0.95)] if latencies else None,
        "maxMs": latencies[-1] if latencies else None,
        "scopes": {name: {"requests": a, "ok": b} for name, (a, b) in per_scope.items()},
    }


def unsupported_probes(base: str) -> list[dict]:
    index = json.loads((SNAP / "_index.json").read_text("utf-8"))
    months = [name.removeprefix("month=") for name in index["packs"] if name.startswith("month=")]
    probes = [
        ("a month combined with a tier", f"/overview?month={months[0]}&tier=4"),
        ("two filters together", "/overview?tier=4&risk=P1"),
        ("two values of one filter", "/overview?tier=4&tier=3"),
        ("a month that does not exist", "/overview?month=2019-01-31"),
        ("a registered non-default sort on applications", "/metrics/M340202/applications?sort=rfb:desc"),
        ("a legal entity that was never recorded", "/overview?legalEntity=LE0000"),
    ]
    out = []
    with httpx.Client(timeout=30) as client:
        for label, path in probes:
            response = client.get(f"{base}/api/v1/portfolio{path}")
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            code = (body.get("error") or {}).get("code")
            out.append({"probe": label, "path": path, "status": response.status_code, "code": code, "explicit": response.status_code in (400, 503) and bool(code)})
    return out


def agent_probes(base: str) -> list[dict]:
    out = []
    with httpx.Client(timeout=60) as client:
        started = time.perf_counter()
        listing = client.get(f"{base}/api/v1/agents")
        out.append({"probe": "list agents", "status": listing.status_code, "ms": round((time.perf_counter() - started) * 1000), "body": listing.text[:160]})
        started = time.perf_counter()
        sent = client.post(
            f"{base}/api/v1/agents/conversations",
            json={"agentKey": "analysis", "message": "offline check", "context": {"entrySurface": "general", "scope": {"filters": {}}}, "contextHash": "x", "clientRequestId": "outage-walk"},
        )
        out.append({"probe": "start a conversation", "status": sent.status_code, "ms": round((time.perf_counter() - started) * 1000), "body": sent.text[:200]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8082")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="views per scope, for a quick pass")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    started = time.perf_counter()
    first = httpx.get(f"{args.base}/api/v1/portfolio/status", timeout=90)
    first_ms = round((time.perf_counter() - started) * 1000)
    report = {
        "base": args.base,
        "firstRequest": {"status": first.status_code, "ms": first_ms, "source": first.json().get("meta", {}).get("source") if first.status_code == 200 else None},
        "walk": walk(args.base, args.threads, args.limit),
        "unsupported": unsupported_probes(args.base),
        "agents": agent_probes(args.base),
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    walk_ok = report["walk"]["failureCount"] == 0
    explicit = all(item["explicit"] for item in report["unsupported"])
    return 0 if walk_ok and explicit else 1


if __name__ == "__main__":
    sys.exit(main())
