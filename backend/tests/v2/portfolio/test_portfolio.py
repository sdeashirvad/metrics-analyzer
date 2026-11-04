"""Pure portfolio checks. These tests do not open Snowflake."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.common.v2_envelope import error_body, ok
from app.common.v2_errors import V2Error, conflict, not_found, unavailable, validation
from app.portfolio.definitions import (
    DEFINITIONS_VERSION,
    classify_denominator,
    get,
    provisional_rate,
    public_definitions,
    rate_change_pp,
    share,
)
from app.portfolio.fallback import applications_data, latest_month, org_data, overview_data, risk_data, trends_data
from app.portfolio.fallback import _load as load_extract
from app.portfolio.month import previous_calendar_month, prior_in_index, resolve_month
from app.portfolio.repository import scope_sql
from app.portfolio.router import router
from app.portfolio.scope import APP_SORT, METRIC_SORT, Scope, parse_page, parse_q, parse_scope, parse_sort, validate_scope_values
from app.portfolio.services.investigations import agent_analysis_ref
from app.portfolio.support import nc_since

_BACKEND = Path(__file__).resolve().parents[3]


def _imports_agents(module) -> bool:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        if any(name == "app.agents" or name.startswith("app.agents.") for name in names):
            return True
    return False


def test_explicit_month_wins_without_a_lookup(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("month lookup should not run")

    monkeypatch.setattr("app.portfolio.month.latest_reporting_month", fail)
    assert resolve_month("2025-11-30", connection="unused", known_latest="2025-12-31") == ("2025-11-30", "selected")
    assert resolve_month(None, known_latest="2025-12-31") == ("2025-12-31", "latest_available")
    assert resolve_month("  ", known_latest="2025-12-31") == ("2025-12-31", "latest_available")


def test_previous_calendar_month_and_index():
    assert previous_calendar_month("2026-03-31") == "2026-02-28"
    assert previous_calendar_month("2026-01-31") == "2025-12-31"
    assert prior_in_index("2026-03-31", ["2026-01-31", "2026-03-31"]) is None
    assert prior_in_index("2026-03-31", ["2026-02-28", "2026-03-31"]) == "2026-02-28"


def test_definitions_registry():
    assert DEFINITIONS_VERSION == "pd-1"
    assert len(public_definitions()["definitions"]) == 19
    assert len(public_definitions()["conventions"]) == 10
    rate = get("PD-01")
    assert rate["status"] == "provisional"
    assert "SUM(IS_NUMERATOR) / SUM(IS_DENOMINATOR)" in rate["definition"]
    assert get("PD-13")["status"] == "not_available"
    assert "family" in get("PD-13")["definition"].lower() or "not" in get("PD-13")["definition"].lower()
    group = get("PD-19")
    assert "groups by denominator treatment only" in group["definition"].lower()
    assert "not a business family" in group["limitations"].lower()
    assert get("PD-19")["sinceVersion"] == "pd-1"
    profile = public_definitions()["classification"]
    assert profile["provisional"] is True
    assert profile["rate"]["greenBelow"] == 0.45
    assert profile["rate"]["amberBelow"] == 0.60
    assert profile["rate"]["unit"] == "fraction"
    assert profile["applicationGreen"]["testResult"] == "Pass"
    with pytest.raises(KeyError):
        get("PD-00")


def test_provisional_rate_formula():
    assert provisional_rate(34, 62) == 0.548387
    assert provisional_rate(33, 56) == 0.589286
    assert rate_change_pp(0.548387, 0.589286) == -4.0899
    assert provisional_rate(1, 0) is None
    assert rate_change_pp(0.5, None) is None
    assert share(300, 923) == 0.325027
    assert share(278, 937) == 0.296692
    assert rate_change_pp(share(300, 923), share(278, 937)) == 2.8335
    assert share(1, 0) is None
    assert classify_denominator(0, 0) == "UNDETERMINED"
    assert classify_denominator(4, 4) == "INCLUDES_PENDING"
    assert classify_denominator(4, 0) == "EXCLUDES_PENDING"
    assert classify_denominator(4, 1) == "MIXED"
    from app.portfolio.definitions import classify_rate, metric_row_is_green
    from app.portfolio.services.metrics import _sort_register
    from app.portfolio.support import paginate

    assert classify_rate(0.449999) == "green"
    assert classify_rate(0.45) == "amber"
    assert classify_rate(0.599999) == "amber"
    assert classify_rate(0.60) == "red"
    assert classify_rate(None) == "unclassified"
    assert metric_row_is_green("Compliant", "Test_Complete", "Pass") is True
    assert metric_row_is_green("Pending", "Test_Complete", "Pass") is False
    assert metric_row_is_green("Not_Applicable", "Exempt", None) is False
    assert metric_row_is_green("Compliant", "Test_Complete", "Fail") is False
    rows = [
        {"metricId": "M000001", "rag": "red", "applications": 1, "nonCompliantApplications": 1, "rate": {"rate": 0.7, "deltaPp": None}},
        {"metricId": "M000002", "rag": "green", "applications": 1, "nonCompliantApplications": 1, "rate": {"rate": 0.3, "deltaPp": None}},
        {"metricId": "M000003", "rag": "amber", "applications": 1, "nonCompliantApplications": 1, "rate": {"rate": 0.5, "deltaPp": None}},
        {"metricId": "M000004", "rag": "red", "applications": 1, "nonCompliantApplications": 1, "rate": {"rate": 0.8, "deltaPp": None}},
    ]
    ordered = _sort_register(rows, "rag", "desc")
    assert [item["rag"] for item in ordered] == ["red", "red", "amber", "green"]
    reds = [item for item in ordered if item["rag"] == "red"]
    page_one, meta = paginate(reds, 1, 1)
    page_two, _ = paginate(reds, 2, 1)
    assert meta["totalItems"] == 2
    assert page_one[0]["rag"] == "red" and page_two[0]["rag"] == "red"
    assert page_one[0]["metricId"] != page_two[0]["metricId"]


def test_envelope_and_errors():
    body = ok(
        {"value": 1},
        request_id="abc",
        source="snowflake",
        definitions_version="pd-1",
        dataset={"version": "v1-seed20261103", "rowCount": 3, "promotedAt": None},
        cache={"hit": False, "ageSeconds": 0, "ttlSeconds": 600},
        as_of="2025-12-31",
    )
    assert set(body) == {"data", "meta"}
    assert body["data"] == {"value": 1}
    meta = body["meta"]
    assert meta["contractVersion"] == "2.0.0"
    assert meta["definitionsVersion"] == "pd-1"
    assert meta["requestId"] == "abc"
    assert meta["generatedAt"].endswith("Z")
    assert meta["asOf"] == "2025-12-31"
    assert meta["source"] == "snowflake"
    assert meta["dataset"]["rowCount"] == 3
    assert meta["warnings"] == []
    assert "lineage" not in meta

    err = error_body(validation("Bad sort.", code="UNSUPPORTED_SORT", field="sort", field_code="UNSUPPORTED_SORT"), "req")
    assert err["error"]["code"] == "UNSUPPORTED_SORT"
    assert err["error"]["retryable"] is False
    assert err["error"]["requestId"] == "req"
    assert err["error"]["fieldErrors"][0]["field"] == "sort"
    assert not_found("METRIC_NOT_FOUND", "Metric was not found.").status_code == 404
    assert conflict("RUN_IN_PROGRESS", "A run is in progress.").status_code == 409
    assert unavailable("down").retryable is True
    packaged = error_body(unavailable("no extract", code="FALLBACK_UNSUPPORTED"), "req")
    assert packaged["error"]["retryable"] is False
    assert packaged["error"]["code"] == "FALLBACK_UNSUPPORTED"


def test_hostile_sort_and_filter():
    with pytest.raises(V2Error) as exc:
        parse_sort("name; DROP TABLE:desc", APP_SORT, ("name", "asc"))
    assert exc.value.code == "UNSUPPORTED_SORT"
    assert exc.value.status_code == 400

    with pytest.raises(V2Error) as exc:
        parse_sort("openFindings:desc", METRIC_SORT, ("applications", "desc"))
    assert exc.value.code == "UNSUPPORTED_SORT"

    with pytest.raises(V2Error) as exc:
        parse_scope({"risk": ["' OR 1=1 --"]})
    assert exc.value.code == "UNKNOWN_FILTER_VALUE"

    with pytest.raises(V2Error) as exc:
        parse_scope({"l1": ["A" * 101]})
    assert exc.value.field_errors[0]["code"] == "TOO_LONG"

    with pytest.raises(V2Error) as exc:
        parse_scope({"risk": ["P1"] * 51})
    assert exc.value.field_errors[0]["code"] == "TOO_MANY"

    with pytest.raises(V2Error) as exc:
        parse_q({"q": ["x" * 41]})
    assert exc.value.field_errors[0]["code"] == "TOO_LONG"

    with pytest.raises(V2Error) as exc:
        parse_scope({"orgTree": ["BU; drop"]})
    assert exc.value.code == "VALIDATION_FAILED"

    with pytest.raises(V2Error) as exc:
        parse_page({"pageSize": ["100 OR 1=1"]})
    assert exc.value.code == "VALIDATION_FAILED"

    with pytest.raises(V2Error) as exc:
        parse_scope({"month": ["2025-11-30;drop"]})
    assert exc.value.code == "UNKNOWN_MONTH"

    with pytest.raises(V2Error) as exc:
        parse_scope({"tier": ["9"]})
    assert exc.value.code == "UNKNOWN_FILTER_VALUE"

    scope = parse_scope({"risk": ["P9"], "orgTree": ["BUSINESS_ORG"]})
    catalog = {
        "risks": ["P1", "P2"],
        "lifecycles": ["Production"],
        "legalEntities": ["LE1"],
        "trees": {
            "BUSINESS_ORG": {"level1": ["Super_Division_01"], "level2": ["Division_01"]},
            "BU": {"level1": [], "level2": []},
        },
    }
    with pytest.raises(V2Error) as exc:
        validate_scope_values(scope, catalog)
    assert exc.value.code == "UNKNOWN_FILTER_VALUE"


def test_scope_sql_binds_values():
    scope = Scope(risk=("P1",), l1=("Super_Division_01",), tier=(1,), ma="Y")
    params: dict = {}
    sql = scope_sql(scope, params, month="2025-12-31")
    assert "P1" not in sql
    assert "Super_Division_01" not in sql
    assert "2025-12-31" not in sql
    assert "ASSET_RISK_RATING_2" in sql
    assert "SUPER_DIVISION" in sql
    assert "DROP" not in sql.upper()
    assert set(params.values()) >= {"P1", "Super_Division_01", 1, "Y", "2025-12-31"}


def test_non_compliant_since_rules():
    first = "2025-11-30"
    assert nc_since({"2025-11-30": False, "2025-12-31": True, "2026-01-31": True}, "2026-01-31", first) == "2025-12-31"
    assert nc_since({"2025-11-30": True, "2025-12-31": True}, "2025-12-31", first) is None
    assert nc_since({"2025-11-30": True, "2026-01-31": True}, "2026-01-31", first) == "2026-01-31"
    assert nc_since({"2026-01-31": False}, "2026-01-31", first) is None


def test_agent_analysis_is_not_run_without_a_narrative():
    blank = agent_analysis_ref(None)
    supplied = agent_analysis_ref("v1.payload.signature")
    for ref in (blank, supplied):
        assert ref["status"] == "NOT_RUN"
        assert ref["source"] is None
        assert ref["precomputed"] is None
        assert ref["conversationId"] is None
        assert ref["runId"] is None
        assert ref["label"] == "Agent-generated. Hypotheses are not established."
    import app.portfolio.services.investigations as investigations

    assert not _imports_agents(investigations)


def test_router_exports_portfolio_routes():
    assert router.prefix == "/api/v1/portfolio"
    paths = {route.path for route in router.routes}
    expected = {
        "/api/v1/portfolio/status",
        "/api/v1/portfolio/filters",
        "/api/v1/portfolio/definitions",
        "/api/v1/portfolio/overview",
        "/api/v1/portfolio/trends",
        "/api/v1/portfolio/distributions/compliance",
        "/api/v1/portfolio/distributions/testing",
        "/api/v1/portfolio/distributions/{dimension}",
        "/api/v1/portfolio/org/contribution",
        "/api/v1/portfolio/data-coverage",
        "/api/v1/portfolio/applications",
        "/api/v1/portfolio/metrics",
        "/api/v1/portfolio/metrics/{metric_id}/preview",
        "/api/v1/portfolio/metrics/{metric_id}",
        "/api/v1/portfolio/metrics/{metric_id}/trend",
        "/api/v1/portfolio/metrics/{metric_id}/breakdowns",
        "/api/v1/portfolio/metrics/{metric_id}/applications",
        "/api/v1/portfolio/applications/{eon_id}",
        "/api/v1/portfolio/applications/{eon_id}/history",
        "/api/v1/portfolio/investigations/metrics/{metric_id}",
        "/api/v1/portfolio/investigations/applications/{eon_id}",
    }
    assert expected <= paths


def test_packaged_extracts_keep_source_numbers():
    overview = overview_data()
    raw = load_extract("overview")[0]
    assert overview["month"] == latest_month()
    assert overview["applicationsReporting"]["value"] == int(raw["APPLICATIONS_REPORTING"])
    assert overview["nonCompliant"]["applications"]["value"] == int(raw["NON_COMPLIANT_APPLICATIONS"])
    assert overview["nonCompliant"]["share"]["value"] == share(
        int(raw["NON_COMPLIANT_APPLICATIONS"]), int(raw["APPLICATIONS_REPORTING"])
    )
    assert overview["nonCompliant"]["share"]["definitionId"] == "PD-08"

    points = trends_data(None, None)["points"]
    trend_rows = sorted(load_extract("trends"), key=lambda row: row["REPORTING_MONTHEND_DATE"])
    assert points[0]["applicationsReporting"] == int(trend_rows[0]["APPLICATIONS_REPORTING"])
    assert points[0]["newlyNonCompliant"] is None
    assert int(trend_rows[0]["NEWLY_NON_COMPLIANT"]) == 0
    assert points[-1]["newlyNonCompliant"] == int(trend_rows[-1]["NEWLY_NON_COMPLIANT"])

    risk = {row["RISK_CODE"]: row for row in load_extract("risk")}
    for item in risk_data()["items"]:
        assert item["applicationsReporting"] == int(risk[item["key"]]["APPLICATIONS_REPORTING"])
        assert item["nonCompliantApplications"] == int(risk[item["key"]]["NON_COMPLIANT_APPLICATIONS"])

    org_rows = [row for row in load_extract("org") if row["HIERARCHY_NAME"] == "BUSINESS_ORG"]
    org = org_data(1, None, "nonCompliant", "desc", 1, 100)
    assert org["totals"]["applicationsReporting"] == sum(int(row["APPLICATIONS_REPORTING"]) for row in org_rows)
    assert org["items"]
    assert org["items"][0]["newlyNonCompliant"] is None
    assert org["items"][0]["withoutCompletedTest"] is None

    apps = applications_data(None, None, "openFindings", "desc", 1, 25)
    assert apps["summary"]["matching"] == len(load_extract("applications"))
    assert apps["items"][0]["legalEntityCode"] is None
    assert apps["items"][0]["nonCompliantSince"] is None
    assert apps["page"]["totalItems"] == apps["summary"]["matching"]


def test_v2_code_has_no_hardcoded_dataset_month():
    roots = [_BACKEND / "app" / "portfolio", _BACKEND / "app" / "common"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "2026-10-31" not in text, path.name
            assert "app.agents" not in text
