"""Portfolio HTTP routes. Not mounted on the legacy app."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.common.v2_errors import V2Route
from app.portfolio.services import applications, dashboard, investigations, metrics

router = APIRouter(prefix="/api/v1/portfolio", route_class=V2Route)


@router.get("/status")
def portfolio_status(request: Request):
    return dashboard.status(request)


@router.get("/filters")
def portfolio_filters(request: Request):
    return dashboard.filters(request)


@router.get("/definitions")
def portfolio_definitions(request: Request):
    return dashboard.definitions(request)


@router.get("/overview")
def portfolio_overview(request: Request):
    return dashboard.overview(request)


@router.get("/trends")
def portfolio_trends(request: Request):
    return dashboard.trends(request)


@router.get("/distributions/compliance")
def portfolio_compliance(request: Request):
    return dashboard.compliance(request)


@router.get("/distributions/testing")
def portfolio_testing(request: Request):
    return dashboard.testing(request)


@router.get("/distributions/{dimension}")
def portfolio_distribution(request: Request, dimension: str):
    return dashboard.distribution(request, dimension)


@router.get("/org/contribution")
def portfolio_org(request: Request):
    return dashboard.org_contribution(request)


@router.get("/data-coverage")
def portfolio_coverage(request: Request):
    return dashboard.data_coverage(request)


@router.get("/applications")
def portfolio_applications(request: Request):
    return dashboard.applications(request)


@router.get("/metrics")
def portfolio_metrics(request: Request):
    return metrics.register(request)


@router.get("/metrics/{metric_id}/preview")
def portfolio_metric_preview(request: Request, metric_id: str):
    return metrics.preview(request, metric_id)


@router.get("/metrics/{metric_id}/trend")
def portfolio_metric_trend(request: Request, metric_id: str):
    return metrics.trend(request, metric_id)


@router.get("/metrics/{metric_id}/breakdowns")
def portfolio_metric_breakdowns(request: Request, metric_id: str):
    return metrics.breakdowns(request, metric_id)


@router.get("/metrics/{metric_id}/applications")
def portfolio_metric_applications(request: Request, metric_id: str):
    return metrics.metric_applications(request, metric_id)


@router.get("/metrics/{metric_id}")
def portfolio_metric(request: Request, metric_id: str):
    return metrics.summary(request, metric_id)


@router.get("/applications/{eon_id}/history")
def portfolio_application_history(request: Request, eon_id: str):
    return applications.history(request, eon_id)


@router.get("/applications/{eon_id}")
def portfolio_application(request: Request, eon_id: str):
    return applications.detail(request, eon_id)


@router.get("/investigations/metrics/{metric_id}")
def portfolio_metric_investigation(request: Request, metric_id: str):
    return investigations.metric_investigation(request, metric_id)


@router.get("/investigations/applications/{eon_id}")
def portfolio_application_investigation(request: Request, eon_id: str):
    return investigations.application_investigation(request, eon_id)
