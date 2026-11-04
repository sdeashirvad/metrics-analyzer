"""Context items each entry surface is allowed to hand to an agent."""

from __future__ import annotations

from dataclasses import dataclass

SURFACES = (
    "general",
    "dashboard",
    "register_preview",
    "metric_summary",
    "metric_investigation",
    "application_investigation",
)
METRIC_SURFACES = frozenset({"register_preview", "metric_summary", "metric_investigation"})
APPLICATION_SURFACES = frozenset({"application_investigation"})
FILTER_SURFACES = frozenset({"dashboard", "register_preview", "metric_summary", "metric_investigation"})

DEFINITION_IDS = {
    "general": ["PD-03", "PD-04", "PD-05", "PD-06", "PD-07", "PD-08", "PD-10", "PD-11", "PD-18"],
    "dashboard": ["PD-03", "PD-04", "PD-05", "PD-06", "PD-07", "PD-08", "PD-10", "PD-11", "PD-18"],
    "register_preview": ["PD-01", "PD-02", "PD-13", "PD-14", "PD-15", "PD-16", "PD-19"],
    "metric_summary": ["PD-01", "PD-02", "PD-13", "PD-14", "PD-15", "PD-16", "PD-19"],
    "metric_investigation": ["PD-01", "PD-02", "PD-13", "PD-14", "PD-15", "PD-16", "PD-19"],
    "application_investigation": ["PD-03", "PD-04", "PD-05", "PD-06", "PD-07", "PD-09", "PD-17"],
}

SURFACE_LABELS = {
    "general": "General",
    "dashboard": "Dashboard",
    "register_preview": "Register preview",
    "metric_summary": "Metric summary",
    "metric_investigation": "Metric investigation",
    "application_investigation": "Application investigation",
}


@dataclass(frozen=True)
class ItemSpec:
    key: str
    label: str
    kind: str
    required: bool
    default_included: bool
    sensitive: bool
    surfaces: frozenset[str]


def _item(key, label, kind, required, default, sensitive, surfaces) -> ItemSpec:
    return ItemSpec(key, label, kind, required, default, sensitive, frozenset(surfaces))


CATALOGUE: tuple[ItemSpec, ...] = (
    _item("ground_rules", "Ground rules", "ground_rules", True, True, False, SURFACES),
    _item("definitions", "Definitions", "definition", True, True, False, SURFACES),
    _item("scope", "Scope", "scope", True, True, False, SURFACES),
    _item("filters", "Filters", "filters", False, True, False, FILTER_SURFACES),
    _item("portfolio_kpis", "Portfolio KPIs", "kpis", False, True, False, ("general", "dashboard")),
    _item("portfolio_trend", "Portfolio trend", "trend", False, False, False, ("general", "dashboard")),
    _item("org_contribution", "Organisation contribution", "breakdown", False, True, False, ("dashboard",)),
    _item("attention_summary", "Attention", "kpis", False, True, False, ("dashboard",)),
    _item("data_coverage", "Data coverage", "coverage", False, True, False, ("general", "dashboard")),
    _item("metric_definition", "Definition (provisional)", "definition", False, True, False, METRIC_SURFACES),
    _item("metric_kpis", "Current values", "kpis", False, True, False, METRIC_SURFACES),
    _item("metric_trend", "Metric trend", "trend", False, True, False, METRIC_SURFACES),
    _item("metric_org_breakdown", "Organisation breakdown", "breakdown", False, True, False, METRIC_SURFACES),
    _item("metric_applications", "Non-compliant applications (sample)", "applications", False, False, False, METRIC_SURFACES),
    _item("application_attributes", "Application attributes", "attributes", False, True, False, APPLICATION_SURFACES),
    _item("application_status", "Application status", "kpis", False, True, False, APPLICATION_SURFACES),
    _item("application_history", "Application history", "history", False, True, False, APPLICATION_SURFACES),
    _item("application_peers", "Peers", "peers", False, True, False, APPLICATION_SURFACES),
    _item("owner_names", "Owner names", "owners", False, False, True, APPLICATION_SURFACES),
)

BY_KEY = {item.key: item for item in CATALOGUE}


def for_surface(surface: str) -> list[ItemSpec]:
    return [item for item in CATALOGUE if surface in item.surfaces]
