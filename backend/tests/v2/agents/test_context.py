import hashlib
import json

from app.agents.context.render import compose_first_message, context_hash, ma2_ref
from app.agents.threads import first_run_body


def test_context_hash_is_the_contract_preimage():
    scope = {
        "eonId": None,
        "filters": {},
        "metricId": "M000001",
        "month": "2026-11-30",
        "monthSource": "selected",
    }
    items = ["definitions", "ground_rules", "scope"]
    rendered = "Context supplied by the application.\nScope line."
    digest = context_hash(
        definitions_version="pd-1",
        promoted_at=None,
        scope=scope,
        item_keys=items,
        rendered_text=rendered,
    )
    canonical = json.dumps({"items": sorted(items), "scope": scope}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    material = "\n".join(["ma2-context-v1", "pd-1", "", canonical, rendered])
    assert digest == hashlib.sha256(material.encode("utf-8")).hexdigest()


def test_first_message_wraps_scope_and_reference():
    ref = ma2_ref(
        agent_key="data",
        client_request_id="11111111-1111-1111-1111-111111111111",
        context_hash="a" * 64,
        definitions_version="pd-1",
        entry_surface="metric_summary",
        month="2026-11-30",
        month_source="selected",
        metric_id="M000001",
        eon_id=None,
        created_at="2026-11-04T00:00:00Z",
    )
    text = compose_first_message(
        rendered="Context supplied by the application. It is the scope of the question. Do not assume anything not listed.\nMetric M000001.",
        entry_surface="metric_summary",
        month="2026-11-30",
        metric_id="M000001",
        eon_id=None,
        filters={},
        question="How many applications reported?",
        ref=ref,
    )
    assert text.splitlines()[-1].startswith("MA2-REF v1")
    assert "ctx=aaaaaaaaaaaa " in text
    assert text.count("How many applications reported?") == 1
    assert "thread_id" not in text
    encoded = next(line for line in text.splitlines() if line.startswith("{"))
    payload = json.loads(encoded)
    assert payload["user_question"] == "How many applications reported?"
    assert payload["entry_surface"] == "register_row"
    assert payload["metric_id"] == "M000001"
    assert payload["active_filters"] == {}
    body = first_run_body(text)
    assert body["messages"][0]["content"][0]["text"] == text
    assert "thread_id" not in body


def test_register_preview_reads_existing_metric_helpers(monkeypatch):
    from app.agents.context.builder import build_preview
    from app.portfolio.services import metrics as metric_services

    def preview(request, metric_id):
        assert metric_id == "M384010"
        assert request.query_params.get("month") == "2026-10-31"
        assert request.query_params.get("orgTree") == "BUSINESS_ORG"
        return {
            "data": {
                "rate": {"numerator": 47, "denominator": 102, "rate": 0.461, "priorRate": 0.5, "deltaPp": -3.9},
                "definition": {"denominatorScope": "INCLUDES_PENDING"},
                "coverage": {"applications": 119, "metricRows": 119, "nonCompliantRows": 36},
            },
            "meta": {"contractVersion": "2.0.0"},
        }

    def trend(request, metric_id):
        return {"data": {"points": [{"month": "2026-10-31", "observed": True, "rate": 0.461}]}, "meta": {}}

    def breakdowns(request, metric_id):
        assert request.query_params.get("dimension") == "org"
        raise RuntimeError("breakdown unavailable")

    monkeypatch.setattr(metric_services, "preview", preview)
    monkeypatch.setattr(metric_services, "trend", trend)
    monkeypatch.setattr(metric_services, "breakdowns", breakdowns)
    preview_body = build_preview({
        "entrySurface": "register_preview",
        "scope": {"metricId": "M384010", "month": "2026-10-31", "filters": {"orgTree": "BUSINESS_ORG"}},
    })
    text = preview_body["rendered"]["text"]
    assert "Metric: M384010." in text
    assert "2026-10-31" in text
    assert "No additional filters." in text
    assert "Numerator 47, denominator 102, provisional rate 0.461." in text
    assert "2026-10-31: provisional rate 0.461." in text
    assert "Figures for this item were not available from the portfolio service." in text
    assert preview_body["scope"]["metricId"] == "M384010"
    assert any(item["code"] == "PORTFOLIO_CONTEXT_UNAVAILABLE" for item in preview_body["warnings"])


def test_dashboard_agent_status_matches_agent_availability():
    from app.agents.limits import memory
    from app.portfolio.services.dashboard import agent_status

    memory.reset()
    assert memory.availability() == "available"
    assert agent_status() == {"analysis": "available", "data": "available"}
