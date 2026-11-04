"""Generate prepared Analysis agent investigations for every metric in the register.

Operator command. It uses the existing Analysis agent and the existing conversation
code, one new conversation per metric, and writes JSON bundles under
`fallback_assets/v2/investigations/`. It is not a chat feature.

    python -m app.agents.prepare_investigations                  # every register metric, latest month
    python -m app.agents.prepare_investigations --metric M340202 # one metric
    python -m app.agents.prepare_investigations --force          # regenerate even if current
    python -m app.agents.prepare_investigations --concurrency 2 --month 2026-10-31

Rules:
- The metric list comes from the live register, never from a hardcoded list.
- An already valid current bundle is skipped unless --force is passed.
- A failed or invalid generation never replaces the last known-good file.
- Figures and the provisional band come from the central registry, not from the agent.
- Concurrency is bounded and the existing agent limits are respected by waiting, not bypassed.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.agents.context.builder import build_preview
from app.agents.conversations import create_conversation, get_run
from app.agents.faults import ApiFault
from app.agents.registry import ANALYSIS, SNOWFLAKE_AGENTS
from app.agents.tokens import signing_key
from app.common.v2_envelope import DATASET_VERSION
from app.config import load_settings
from app.db.connection import connect
from app.portfolio.definitions import (
    DEFINITIONS_VERSION,
    RATE_AMBER_BELOW,
    RATE_GREEN_BELOW,
    classify_rate,
    provisional_rate,
)
from app.portfolio.prepared import (
    BUNDLE_DIR,
    band_consistency,
    bundle_is_current,
    can_publish,
    publish_bundle,
    reconcile_context,
    source_fact_validation,
    write_report,
)
from app.portfolio.repository import latest_reporting_month, metric_month_aggregates, snapshot
from app.portfolio.scope import Scope

_POLL_SECONDS = 5
_WAIT_SECONDS = 480
_RETRY_LIMIT = 8
_BAND_LABEL = {"green": "Green (healthy)", "amber": "Amber (watch)", "red": "Red (needs attention)", "unclassified": "unclassified"}


def question(metric: dict, month: str) -> str:
    """A neutral request. It states the central figures and band so the agent cannot invent them."""

    rate = metric.get("rate")
    rate_text = "no rate (the denominator is 0)" if rate is None else f"{rate * 100:.1f}% ({metric['numerator']} of {metric['denominator']})"
    band = _BAND_LABEL.get(str(metric.get("rag")), "unclassified")
    return (
        f"Write a concise investigation note for metric {metric['metricId']} for the reporting month {month}. "
        f"Its provisional rate is {rate_text} and its provisional band is {band}. "
        f"Green is below {RATE_GREEN_BELOW:.0%}, amber is below {RATE_AMBER_BELOW:.0%}, and red is from there up. A higher rate is worse. "
        "Cover, in this order: the executive finding; current status and period; important movement against the prior month; "
        "the organisations, legal entities or applications that contribute most; testing or exception observations; "
        "areas that deserve further investigation; and the limitations of the evidence. "
        "Describe the metric's actual state. Do not describe a concern when the band is green, and do not describe it as healthy when the band is amber or red. "
        "Separate observed data from hypotheses. Do not invent causes, owners or completed remediation."
    )


def candidates(connection, month: str, only: set[str] | None = None) -> list[dict]:
    scope = Scope()
    rows = metric_month_aggregates(connection, scope)
    metrics = []
    for row in rows:
        metric_id = str(row["METRIC_ID"])
        if str(row["MONTH_END"]) != month:
            continue
        if only and metric_id not in only:
            continue
        numerator = int(row.get("NUMERATOR") or 0)
        denominator = int(row.get("DENOMINATOR") or 0)
        rate = provisional_rate(numerator, denominator)
        metrics.append({
            "metricId": metric_id,
            "nonCompliant": int(row.get("NON_COMPLIANT") or 0),
            "applications": int(row.get("APPLICATIONS") or 0),
            "failedTests": int(row.get("RESULT_FAIL") or 0),
            "rag": classify_rate(rate),
            "numerator": numerator,
            "denominator": denominator,
            "rate": rate,
        })
    return sorted(metrics, key=lambda item: item["metricId"])


def assemble(metric: dict, produced: dict, *, month: str, source: dict | None = None) -> dict:
    content = produced.get("content") if isinstance(produced.get("content"), dict) else {}
    text = content.get("text") if isinstance(content.get("text"), str) else ""
    stored = produced.get("facts") if isinstance(produced.get("facts"), dict) else {}
    reconciliation = reconcile_context(metric, stored)
    fact_status, limitation = source_fact_validation(text, metric)
    band_status, band_note = band_consistency(text, metric.get("rag"))
    if band_status == "FAIL":
        limitation = band_note
    return {
        "metricId": metric["metricId"],
        "displayName": metric["metricId"],
        "scopeType": "metric",
        "reportingDate": month,
        "dataAsOf": month,
        "rag": metric.get("rag"),
        "scope": {
            "orgTree": "BUSINESS_ORG",
            "l1": [],
            "l2": [],
            "legalEntity": [],
            "tier": [],
            "risk": [],
            "lifecycle": [],
            "ma": None,
        },
        "datasetVersion": DATASET_VERSION,
        "definitionsVersion": DEFINITIONS_VERSION,
        "sourceSnapshot": source,
        "agent": SNOWFLAKE_AGENTS[ANALYSIS],
        "generatedAt": produced.get("generatedAt"),
        "threadId": produced.get("threadId"),
        "conversationId": produced.get("conversationId"),
        "runId": produced.get("runId"),
        "messageId": produced.get("messageId"),
        "context_reconciliation": reconciliation,
        "source_fact_validation": fact_status,
        "band_consistency": band_status,
        "source_fact_limitation": limitation,
        "agent_response_status": produced.get("agent_response_status") or "FAILED",
        "content": content,
    }


def consider(metric: dict, existing: dict | None, produced: dict | None, *, force: bool, month: str, source: dict | None = None) -> dict:
    """Publish only a completed, parsed, reconciled and consistent result. Leave a valid file in place otherwise."""

    if existing and bundle_is_current(existing, month=month, dataset_version=DATASET_VERSION, definitions_version=DEFINITIONS_VERSION) and not force:
        return {"metricId": metric["metricId"], "status": "skipped", "threadId": existing.get("threadId"), "error": None}
    if produced is None:
        return {"metricId": metric["metricId"], "status": "failed", "threadId": None, "error": "The agent run did not return a result."}
    document = assemble(metric, produced, month=month, source=source)
    if not can_publish(document):
        return {
            "metricId": metric["metricId"],
            "status": "not_published",
            "threadId": produced.get("threadId"),
            "error": document.get("source_fact_limitation") or "The analysis was incomplete or its context did not reconcile.",
            "context_reconciliation": document["context_reconciliation"],
            "source_fact_validation": document["source_fact_validation"],
            "band_consistency": document["band_consistency"],
            "agent_response_status": document["agent_response_status"],
        }
    publish_bundle(document)
    return {
        "metricId": metric["metricId"],
        "status": "published",
        "threadId": document.get("threadId"),
        "error": None,
        "context_reconciliation": document["context_reconciliation"],
        "source_fact_validation": document["source_fact_validation"],
        "band_consistency": document["band_consistency"],
        "agent_response_status": document["agent_response_status"],
    }


def _context_facts(rendered: str, metric: dict) -> dict:
    """Figures stated in the metric context, compared later with the source query."""

    facts = {
        "nonCompliant": -1,
        "applications": -1,
        "numerator": -1,
        "denominator": -1,
        "rate": -1,
    }
    match = re.search(r"Numerator\s+(\d+),\s+denominator\s+(\d+),\s+provisional rate\s+([0-9]+(?:\.[0-9]+)?|None)", rendered)
    if match:
        facts["numerator"] = int(match.group(1))
        facts["denominator"] = int(match.group(2))
        facts["rate"] = None if match.group(3) == "None" else float(match.group(3))
    non_compliant = re.search(r"Non-compliant metric rows:\s+(\d+)", rendered)
    if non_compliant:
        facts["nonCompliant"] = int(non_compliant.group(1))
    applications = re.search(r"Metric rows in scope:\s+(\d+)", rendered)
    if applications:
        facts["applications"] = int(applications.group(1))
    if metric.get("rate") is None:
        facts["rate"] = None if facts["rate"] == -1 else facts["rate"]
    return facts


def _with_backoff(call):
    """Wait out the existing agent limits instead of bypassing them."""

    for attempt in range(_RETRY_LIMIT):
        try:
            return call()
        except ApiFault as fault:
            if not fault.retryable or attempt == _RETRY_LIMIT - 1:
                raise
            wait = max(2.0, min(120.0, (fault.retry_after_ms or 5000) / 1000.0))
            time.sleep(wait)
    raise RuntimeError("unreachable")


def run_metric(settings, key: bytes, metric: dict, month: str) -> dict:
    scope = {"month": month, "metricId": metric["metricId"], "filters": {"orgTree": "BUSINESS_ORG"}}
    preview = build_preview({"entrySurface": "metric_investigation", "scope": scope})
    _status, created = _with_backoff(
        lambda: create_conversation(
            settings,
            {
                "agentKey": ANALYSIS,
                "message": question(metric, month),
                "context": {"entrySurface": "metric_investigation", "scope": scope},
                "contextHash": preview["contextHash"],
                "clientRequestId": str(uuid.uuid4()),
            },
            key,
        )
    )
    run_id = created["run"]["runId"]
    deadline = time.monotonic() + _WAIT_SECONDS
    last = created["run"]
    while time.monotonic() < deadline:
        last = get_run(settings, run_id, key)
        if last.get("status") in {"COMPLETED", "FAILED"}:
            break
        time.sleep(_POLL_SECONDS)
    message = last.get("message") if isinstance(last.get("message"), dict) else {}
    content = message.get("content") if isinstance(message.get("content"), dict) else {}
    return {
        "content": content,
        "conversationId": created["conversation"]["conversationId"],
        "threadId": created["conversation"]["threadId"],
        "runId": run_id,
        "messageId": message.get("messageId"),
        "generatedAt": last.get("finishedAt") or created["conversation"]["createdAt"],
        "agent_response_status": "COMPLETED" if last.get("status") == "COMPLETED" and content.get("kind") == "analysis" else "FAILED",
        "facts": _context_facts(preview["rendered"]["text"], metric),
    }


def _existing(metric_id: str) -> dict | None:
    path = BUNDLE_DIR / f"{metric_id}.json"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _process(settings, key: bytes, metric: dict, month: str, force: bool, source: dict | None, rejected_dir: str | None = None) -> dict:
    existing = _existing(metric["metricId"])
    current = bool(existing) and bundle_is_current(existing, month=month, dataset_version=DATASET_VERSION, definitions_version=DEFINITIONS_VERSION)
    if current and not force:
        return consider(metric, existing, None, force=False, month=month, source=source)
    produced = None
    error = None
    try:
        produced = run_metric(settings, key, metric, month)
    except Exception as exc:  # one failure must not stop the others
        error = f"{type(exc).__name__}: {exc}"[:300]
    row = consider(metric, existing, produced, force=force, month=month, source=source)
    if rejected_dir and produced and row["status"] == "not_published":
        folder = Path(rejected_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{metric['metricId']}.json").write_text(
            json.dumps({"row": row, "produced": produced, "metric": metric}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if error and row["status"] != "published":
        row["error"] = error
    row["startedAt"] = produced.get("generatedAt") if produced else None
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate prepared Analysis investigations for the metric register.")
    parser.add_argument("--force", action="store_true", help="regenerate even when a current valid bundle exists")
    parser.add_argument("--metric", action="append", default=[], help="limit to a metric id; repeatable")
    parser.add_argument("--month", default=None, help="reporting month, default the latest")
    parser.add_argument("--rejected-dir", default=None, help="write the text of unpublished analyses here for review")
    parser.add_argument("--concurrency", type=int, default=2, help="bounded parallel runs (1 to 4)")
    args = parser.parse_args()
    workers = max(1, min(4, args.concurrency))

    settings = load_settings()
    key = signing_key(settings.snowflake_password)
    with connect(settings) as connection:
        month = args.month or latest_reporting_month(connection)
        chosen = candidates(connection, month, set(args.metric) or None) if month else []
        source = snapshot(connection, month) if month else None
    if args.metric:
        unknown = sorted(set(args.metric) - {item["metricId"] for item in chosen})
        if unknown:
            print(f"Not in the register for {month}: {', '.join(unknown)}")
    print(f"month {month}: {len(chosen)} metrics, concurrency {workers}")

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, settings, key, metric, month, args.force, source, args.rejected_dir): metric["metricId"] for metric in chosen}
        for future in as_completed(futures):
            row = future.result()
            results[row["metricId"]] = row
            print(f"  {row['metricId']}: {row['status']}" + (f" ({row['error']})" if row.get("error") else ""))

    previous: dict[str, dict] = {}
    report_path = BUNDLE_DIR / "generation_report.json"
    if report_path.is_file():
        try:
            old = json.loads(report_path.read_text(encoding="utf-8"))
            if old.get("month") == month:
                previous = {item["metricId"]: item for item in old.get("metrics", [])}
        except (json.JSONDecodeError, KeyError):
            previous = {}
    merged = {**previous, **results}
    write_report({"month": month, "metrics": [merged[name] for name in sorted(merged)]})
    counts: dict[str, int] = defaultdict(int)
    for row in results.values():
        counts[row["status"]] += 1
    print("summary: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items())))


if __name__ == "__main__":
    main()
