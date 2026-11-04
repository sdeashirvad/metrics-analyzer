"""Investigation pages. Agent narratives stay with the agent lane."""

from __future__ import annotations

from app.common.v2_envelope import DATASET_VERSION
from app.portfolio import repository
from app.portfolio.definitions import DEFINITIONS_VERSION, get
from app.portfolio.prepared import analysis_ref, match_metric_bundle
from app.portfolio.month import prior_in_index
from app.portfolio.scope import SCOPE_KEYS, one, parse_bool, parse_choice, parse_eon_id, parse_metric_id
from app.portfolio.services.applications import build_detail, build_history, observed_map
from app.portfolio.services.dashboard import _run, _scoped, _unsupported
from app.portfolio.services.metrics import _composition, _preview_payload, load_metric_context
from app.portfolio.support import nc_run, source_urls

_LABEL = "Agent-generated. Hypotheses are not established."


def agent_analysis_ref(run_id: str | None, bundle: dict | None = None) -> dict:
    """A prepared bundle is returned when one matches. Live runs stay with the browser."""
    return analysis_ref(run_id, bundle, _LABEL)


def metric_investigation(request, metric_id: str):
    metric_id = parse_metric_id(metric_id)
    params, scope, warnings = _scoped(request, set(SCOPE_KEYS) | {"runId", "fallback"})
    parse_choice(params, "fallback", {"precomputed"})
    run_id = one(params, "runId")

    def produce(connection, probe, catalog, resolved):
        preview = _preview_payload(connection, probe, catalog, resolved, metric_id, warnings, summary=False)
        ctx = load_metric_context(connection, probe, catalog, resolved, metric_id)
        month = ctx["month"]
        prior = ctx["prior"]
        eon_rows = repository.metric_eon_rows(connection, resolved, metric_id)
        by_month: dict[str, list] = {}
        for row in eon_rows:
            by_month.setdefault(row["MONTH_END"], []).append(row)
        if prior:
            composition = _composition(by_month.get(prior, []), by_month.get(month, []))
        else:
            composition = _composition([], by_month.get(month, []))
        composition["definitionId"] = "PD-15"
        current_rows = repository.metric_application_rows(connection, resolved, metric_id, month, prior)
        prior_rows = repository.metric_application_rows(connection, resolved, metric_id, prior, None) if prior else []
        level_column = "BU_SUPER_DIVISION" if resolved.org_tree == "BU" else "SUPER_DIVISION"
        flags = list(preview["data"]["flags"])
        bundle = match_metric_bundle(
            metric_id,
            month,
            resolved,
            (probe or {}).get("version") or DATASET_VERSION,
            DEFINITIONS_VERSION,
        )
        if run_id and bundle is None:
            flags.append({
                "code": "RUN_NOT_READ",
                "text": "A run id was supplied. This response does not read that live run.",
            })
        return {
            "data": {
                "metricId": metric_id,
                "month": month,
                "previousMonth": prior,
                "observations": {
                    "rate": preview["data"]["rate"],
                    "compliance": preview["data"]["compliance"],
                    "testing": preview["data"]["testing"],
                    "applications": preview["data"]["coverage"]["applications"],
                    "rag": preview["data"]["rag"],
                },
                "derived": {
                    "rateChange": {"deltaPp": preview["data"]["rate"]["deltaPp"], "definitionId": "PD-16"},
                    "composition": composition,
                    "movement": preview["data"]["movement"],
                    "largestContributors": _contributors(current_rows, prior_rows if prior else None, level_column),
                },
                "sourceRows": source_urls(metric_id, resolved),
                "agentAnalysis": agent_analysis_ref(run_id, bundle),
                "flags": flags,
            },
            "warnings": warnings,
            "asOf": month,
        }

    return _run(
        request,
        f"investigations/metrics/{metric_id}",
        {**scope.cache_params(), "runId": bool(run_id)},
        scope,
        produce,
        _unsupported,
    )


def application_investigation(request, eon_id: str):
    eon_id = parse_eon_id(eon_id)
    params, scope, warnings = _scoped(request, {"month", "metricId", "includeOwners", "runId", "fallback"})
    parse_choice(params, "fallback", {"precomputed"})
    include_owners = parse_bool(params, "includeOwners", default=False)
    metric_id = one(params, "metricId")
    if metric_id:
        metric_id = parse_metric_id(metric_id)
    run_id = one(params, "runId")

    def produce(connection, probe, catalog, resolved):
        detail = build_detail(connection, probe, eon_id, scope.month, include_owners)
        month = detail["data"]["month"]
        history = build_history(connection, probe, eon_id, metric_id)
        rows = repository.application_months(connection, eon_id)
        first = probe["months"][0] if probe["months"] else month
        run = nc_run(observed_map(rows), month, first) if detail["data"]["observed"] else None
        flags = []
        if not detail["data"]["observed"]:
            flags.append({"code": "NOT_OBSERVED", "text": "The application did not report in the requested month."})
        if run_id:
            flags.append({
                "code": "RUN_NOT_READ",
                "text": "A run id was supplied. This response does not read agent runs or write a narrative.",
            })
        flags.append({"code": "PEERS_PROVISIONAL", "text": get("PD-17")["definition"], "definitionId": "PD-17"})
        return {
            "data": {
                "application": detail["data"],
                "history": history["data"],
                "derived": {
                    "nonCompliantRun": run,
                    "peers": detail["data"]["peers"],
                    "definitionIds": ["PD-06", "PD-09", "PD-17"],
                },
                "agentAnalysis": agent_analysis_ref(run_id),
                "flags": flags,
            },
            "warnings": warnings + detail["warnings"],
            "asOf": month,
        }

    return _run(
        request,
        f"investigations/applications/{eon_id}",
        {"metricId": metric_id, "includeOwners": include_owners, "runId": bool(run_id), **scope.cache_params()},
        scope,
        produce,
        _unsupported,
        require_catalog=False,
    )


def _contributors(current_rows: list, prior_rows: list | None, level_column: str) -> list[dict]:
    def grouped(rows, column):
        found = {}
        for row in rows:
            key = "" if row.get(column) is None else str(row.get(column))
            bucket = found.setdefault(key, {"applications": 0, "nonCompliant": 0})
            bucket["applications"] += 1
            if row.get("COMPLIANCE_STATUS") == "Non_Compliant":
                bucket["nonCompliant"] += 1
        return found

    output = []
    for dimension, column in (("org", level_column), ("legalEntity", "LEGAL_ENTITY_CODE")):
        current = grouped(current_rows, column)
        prior = grouped(prior_rows, column) if prior_rows is not None else None
        ranked = sorted(current, key=lambda key: (-current[key]["nonCompliant"], key))[:5]
        for key in ranked:
            change = None if prior is None else current[key]["nonCompliant"] - prior.get(key, {"nonCompliant": 0})["nonCompliant"]
            output.append({
                "dimension": dimension,
                "key": key,
                "nonCompliantApplications": current[key]["nonCompliant"],
                "applications": current[key]["applications"],
                "changeInNonCompliantVsPrior": change,
            })
    return output
