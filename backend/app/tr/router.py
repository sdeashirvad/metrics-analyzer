from fastapi import APIRouter, Query

from app.dq.service import parse_page
from app.fallback import tr as tr_data

router = APIRouter(prefix="/api/v1/tr")


@router.get("/overview")
def overview():
    return tr_data.overview()


@router.get("/metrics")
def metrics(
    q: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    frequency: str | None = None,
    investigation: bool | None = None,
    page: int = Query(1),
    pageSize: int = Query(25),
):
    parse_page(page, pageSize)
    return tr_data.list_metrics(
        q=q,
        domain=domain,
        status=status,
        frequency=frequency,
        investigation=investigation,
        page=page,
        page_size=pageSize,
    )


@router.get("/metrics/{metric_id}")
def metric(metric_id: str):
    return tr_data.metric(metric_id)


@router.get("/metrics/{metric_id}/trend")
def metric_trend(metric_id: str):
    return tr_data.trend(metric_id)


@router.get("/investigations")
def investigation_list():
    return tr_data.investigations()


@router.get("/metrics/{metric_id}/investigation")
def metric_investigation(metric_id: str):
    return tr_data.investigation(metric_id)


@router.get("/metrics/{metric_id}/org")
def metric_org(metric_id: str):
    return tr_data.org(metric_id)
