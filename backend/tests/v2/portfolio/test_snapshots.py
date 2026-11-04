"""Offline serving from recorded packs.

Part one uses a small synthetic pack directory, so the rules are tested exactly: scope matching, re-paging,
register re-slicing and explicit refusal. Part two runs against the packaged assets when they are present:
every recorded scope is read back through the real router with Snowflake made unreachable.
"""

from __future__ import annotations

import gzip
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import ReadTimeout
from app.portfolio import runtime, snapshots
from app.portfolio.cache import response_cache
from app.portfolio.gate import portfolio_gate
from app.portfolio.router import router

LATEST = "2026-10-31"


def _request(path: str, query: str = ""):
    from urllib.parse import parse_qsl

    items = parse_qsl(query, keep_blank_values=True)
    return SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/portfolio" + path),
        query_params=SimpleNamespace(multi_items=lambda: items),
    )


def _metric(metric_id: str, apps: int, nc: int, rag: str, scope: str = "INCLUDES_PENDING") -> dict:
    return {
        "metricId": metric_id,
        "applications": apps,
        "nonCompliantApplications": nc,
        "rag": rag,
        "denominatorScope": scope,
        "rate": {"rate": nc / apps, "deltaPp": 0.0},
        "sparkline": [],
    }


def _register(items: list[dict]) -> dict:
    return {
        "list": True,
        "payload": {
            "data": {
                "items": items,
                "page": {"page": 1, "pageSize": 100, "totalItems": len(items), "totalPages": 1},
                "totals": {"metrics": len(items), "metricsWithRowsInMonth": len(items)},
            },
            "asOf": LATEST,
            "warnings": [],
            "lineage": None,
        },
    }


def _write(directory, signature: str, entries: dict) -> None:
    name = snapshots.pack_name(signature)
    with gzip.open(directory / name, "wt", encoding="utf-8") as handle:
        json.dump({"signature": signature, "entries": entries}, handle)
    path = directory / "_index.json"
    index = json.loads(path.read_text("utf-8")) if path.exists() else {"latestMonth": LATEST, "packs": {}}
    index["packs"][signature] = {"file": name, "entries": len(entries)}
    path.write_text(json.dumps(index), encoding="utf-8")


@pytest.fixture
def packs(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "_DIR", tmp_path)
    snapshots.reset()
    items = [_metric("M1", 100, 10, "green"), _metric("M2", 300, 200, "red"), _metric("M3", 200, 100, "amber", "EXCLUDES_PENDING")]
    _write(tmp_path, "", {"/metrics": _register(items), "/overview": {"list": False, "payload": {"data": {"scope": "default"}, "asOf": LATEST, "warnings": [], "lineage": None}}})
    _write(tmp_path, "month=2026-09-30", {"/overview": {"list": False, "payload": {"data": {"scope": "september"}, "asOf": "2026-09-30", "warnings": [], "lineage": None}}})
    _write(tmp_path, "tier=4", {"/overview": {"list": False, "payload": {"data": {"scope": "tier 4"}, "asOf": LATEST, "warnings": [], "lineage": None}}})
    yield tmp_path
    snapshots.reset()


def test_split_query_canonicalises_scope_and_drops_defaults():
    signature, rest = snapshots.split_query(
        "/metrics",
        [("page", "2"), ("tier", "4"), ("month", LATEST), ("orgTree", "BUSINESS_ORG"), ("tier", "1"), ("unknown", "x")],
        LATEST,
    )
    assert signature == "tier=1,4"
    assert rest == {"page": ["2"]}


def test_snapshot_key_returns_signature_and_view_and_ignores_paging_for_lists():
    assert snapshots.snapshot_key("/metrics", [("page", "3"), ("pageSize", "10")], LATEST) == ("", "/metrics")
    other = snapshots.snapshot_key("/metrics", [("month", "2026-09-30")], LATEST)
    assert other == ("month=2026-09-30", "/metrics")
    assert snapshots.snapshot_key("/overview", [("month", "2026-09-30")], LATEST) != snapshots.snapshot_key("/overview", [], LATEST)


def test_scope_less_routes_always_live_in_the_default_pack():
    assert snapshots.snapshot_key("/definitions", [], LATEST)[0] == ""
    assert snapshots.snapshot_key("/filters", [("month", "2026-09-30")], LATEST)[0] == ""


def test_each_scope_serves_only_its_own_view(packs):
    assert snapshots.lookup(_request("/overview"))["data"]["scope"] == "default"
    assert snapshots.lookup(_request("/overview", "month=2026-09-30"))["data"]["scope"] == "september"
    assert snapshots.lookup(_request("/overview", "tier=4"))["data"]["scope"] == "tier 4"
    assert snapshots.lookup(_request("/overview", f"month={LATEST}"))["data"]["scope"] == "default"


def test_unrecorded_scope_or_combination_is_refused_not_approximated(packs):
    assert snapshots.lookup(_request("/overview", "month=2026-08-31")) is None
    assert snapshots.lookup(_request("/overview", "tier=4&month=2026-09-30")) is None
    assert snapshots.lookup(_request("/overview", "tier=3")) is None
    assert snapshots.lookup(_request("/overview", "legalEntity=LE0000")) is None


def test_register_is_repaged_from_the_stored_list(packs):
    served = snapshots.lookup(_request("/metrics", "pageSize=2&page=2&sort=metricId:asc"))["data"]
    assert [item["metricId"] for item in served["items"]] == ["M3"]
    assert served["page"] == {"page": 2, "pageSize": 2, "totalItems": 3, "totalPages": 2}


def test_register_filters_and_sorts_match_the_live_rules(packs):
    by_rate = snapshots.lookup(_request("/metrics", "sort=rate:desc"))["data"]
    assert [item["metricId"] for item in by_rate["items"]] == ["M2", "M3", "M1"]
    amber = snapshots.lookup(_request("/metrics", "rag=amber"))["data"]
    assert [item["metricId"] for item in amber["items"]] == ["M3"]
    search = snapshots.lookup(_request("/metrics", "q=m2"))["data"]
    assert [item["metricId"] for item in search["items"]] == ["M2"]
    assert search["totals"]["metrics"] == 1
    scoped = snapshots.lookup(_request("/metrics", "denominatorScope=EXCLUDES_PENDING"))["data"]
    assert [item["metricId"] for item in scoped["items"]] == ["M3"]


def test_invalid_paging_and_unknown_sort_are_refused(packs):
    assert snapshots.lookup(_request("/metrics", "pageSize=500")) is None
    assert snapshots.lookup(_request("/metrics", "page=0")) is None
    assert snapshots.lookup(_request("/metrics", "sort=nonsense:desc")) is None


# ---------------------------------------------------------------- packaged assets, through the real router

packaged = pytest.mark.skipif(not (snapshots.directory() / "_index.json").exists() or not snapshots.available(), reason="no recorded packs")


def _client(monkeypatch) -> TestClient:
    def down(*_args, **_kwargs):
        raise ReadTimeout()

    monkeypatch.setattr(runtime, "connect_read", down)
    response_cache.clear()
    portfolio_gate.reset()
    app = FastAPI()
    app.state.settings = object()
    app.include_router(router)
    return TestClient(app)


def _query_of(signature: str) -> str:
    return signature


@packaged
def test_every_recorded_scope_serves_its_register_while_snowflake_is_down(monkeypatch):
    client = _client(monkeypatch)
    scopes = snapshots.scopes()
    assert "" in scopes
    latest = snapshots.latest_month()
    months = [name for name in scopes if name.startswith("month=")]
    assert len(months) == 11, "twelve months in total with the latest one at the default scope"
    for signature in scopes:
        response = client.get(f"/api/v1/portfolio/metrics?{_query_of(signature)}&pageSize=100")
        assert response.status_code == 200, signature
        body = response.json()
        assert body["meta"]["source"] == "packaged", signature
        assert body["data"]["items"], signature
        if signature.startswith("month="):
            assert body["meta"]["asOf"].startswith(signature.removeprefix("month=")), signature
        else:
            assert body["meta"]["asOf"].startswith(latest), signature


@packaged
def test_packaged_register_has_all_24_metrics_with_truthful_source(monkeypatch):
    client = _client(monkeypatch)
    body = client.get("/api/v1/portfolio/metrics?pageSize=100").json()
    assert body["meta"]["source"] == "packaged"
    assert body["data"]["page"]["totalItems"] == 24
    assert len({item["metricId"] for item in body["data"]["items"]}) == 24


@packaged
def test_packaged_routes_for_the_default_scope_are_served(monkeypatch):
    client = _client(monkeypatch)
    for path in (
        "/status",
        "/filters",
        "/definitions",
        "/overview",
        "/trends",
        "/distributions/compliance",
        "/org/contribution",
        "/data-coverage",
        "/applications?attention=nonCompliant&pageSize=5",
    ):
        response = client.get("/api/v1/portfolio" + path)
        assert response.status_code == 200, path
        assert response.json()["meta"]["source"] == "packaged", path


@packaged
def test_an_unpackaged_combination_fails_explicitly(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/v1/portfolio/metrics?month=2026-09-30&tier=4")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "FALLBACK_UNSUPPORTED"
    assert "not packaged" in error["message"]
    assert "unreachable" in error["message"]


@packaged
def test_a_single_filter_at_the_latest_month_is_served_and_differs_from_default(monkeypatch):
    client = _client(monkeypatch)
    default = client.get("/api/v1/portfolio/overview").json()["data"]
    tier = client.get("/api/v1/portfolio/overview?tier=4").json()
    assert tier["meta"]["source"] == "packaged"
    assert tier["data"] != default
