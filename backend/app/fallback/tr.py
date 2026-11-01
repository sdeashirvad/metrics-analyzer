"""Technology Risk is packaged JSON. This provider never opens Snowflake."""

from __future__ import annotations

from app.core.errors import not_found
from app.fallback.assets import read_json, read_metric


def _metric_id(metric_id: str) -> str:
    if not metric_id.startswith("M") or not metric_id[1:].isdigit():
        raise not_found(f"No metric {metric_id} is in the illustrative register.")
    return metric_id


def overview() -> dict:
    return read_json("tr-overview")


def list_metrics(
    *,
    q: str | None,
    domain: str | None,
    status: str | None,
    frequency: str | None,
    investigation: bool | None,
    page: int,
    page_size: int,
) -> dict:
    register = read_json("tr-register")
    items = list(register["items"])

    def matches(item: dict) -> bool:
        metric = item["metric"]
        if domain and metric["domain"] != domain:
            return False
        if status and item["reading"]["status"] != status:
            return False
        if frequency and metric["frequency"] != frequency:
            return False
        if investigation and not item["investigationAvailable"]:
            return False
        if q:
            haystack = f"{metric['id']} {metric['name']} {metric['domain']} {metric['controlId']}".lower()
            if q.strip().lower() not in haystack:
                return False
        return True

    filtered = [item for item in items if matches(item)]
    filtered.sort(
        key=lambda item: (
            {"red": 0, "amber": 1, "insufficient_data": 2, "green": 3}[item["reading"]["status"]],
            item["reading"]["breachedOn"] or "9999-99-99",
            item["metric"]["id"],
        )
    )
    start = (page - 1) * page_size
    return {
        "items": filtered[start : start + page_size],
        "total": len(filtered),
        "page": page,
        "pageSize": page_size,
        "facets": register["facets"],
    }


def metric(metric_id: str) -> dict:
    found = read_metric("metrics", _metric_id(metric_id))
    if not found:
        raise not_found(f"No metric {metric_id} is in the illustrative register.")
    return found


def trend(metric_id: str) -> dict:
    found = read_metric("trends", _metric_id(metric_id))
    if not found:
        raise not_found(f"No metric {metric_id} is in the illustrative register.")
    return found


def investigations() -> dict:
    return read_json("tr-investigations")


def investigation(metric_id: str) -> dict:
    _metric_id(metric_id)
    found = read_metric("investigation", metric_id)
    if not found:
        raise not_found(f"No seeded investigation is available for {metric_id}.")
    return found


def org(metric_id: str) -> dict:
    found = read_metric("org", _metric_id(metric_id))
    if not found:
        raise not_found(f"No metric {metric_id} is in the illustrative register.")
    return found
