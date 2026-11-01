from app.config import Settings
from app.db.connection import fetch_all
from app.db.rows import as_float, iso, rag


def recent_for(connection, settings: Settings, control_ids: list[str], limit: int = 20) -> dict[str, list[dict]]:
    if not control_ids:
        return {}
    placeholders = ", ".join(f"%(id_{index})s" for index in range(len(control_ids)))
    params = {f"id_{index}": control_id for index, control_id in enumerate(control_ids)}
    params["limit"] = limit
    sql = f"""
        SELECT CONTROL_ID, METRIC_DATE, PASS_RATE_PCT, RAG_STATUS
        FROM {settings.qualified("DQ_RESULTS")}
        WHERE CONTROL_ID IN ({placeholders})
        QUALIFY ROW_NUMBER() OVER (PARTITION BY CONTROL_ID ORDER BY METRIC_DATE DESC) <= %(limit)s
        ORDER BY CONTROL_ID, METRIC_DATE
    """
    grouped: dict[str, list[dict]] = {control_id: [] for control_id in control_ids}
    for row in fetch_all(connection, sql, params):
        grouped[row["CONTROL_ID"]].append(
            {
                "date": iso(row["METRIC_DATE"]),
                "passRate": as_float(row["PASS_RATE_PCT"]),
                "status": rag(row["RAG_STATUS"]),
            }
        )
    return grouped


def history(connection, settings: Settings, control_id: str, limit: int | None = None) -> list[dict]:
    limit_sql = ""
    params: dict = {"control_id": control_id}
    if limit is not None:
        limit_sql = "QUALIFY ROW_NUMBER() OVER (ORDER BY METRIC_DATE DESC) <= %(limit)s"
        params["limit"] = limit
    sql = f"""
        SELECT METRIC_DATE, PASS_RATE_PCT, RAG_STATUS, FAILED_RECORDS, TOTAL_RECORDS
        FROM {settings.qualified("DQ_RESULTS")}
        WHERE CONTROL_ID = %(control_id)s
        {limit_sql}
        ORDER BY METRIC_DATE
    """
    return [
        {
            "date": iso(row["METRIC_DATE"]),
            "passRate": as_float(row["PASS_RATE_PCT"]),
            "status": rag(row["RAG_STATUS"]),
            "failed": int(row["FAILED_RECORDS"]),
            "total": int(row["TOTAL_RECORDS"]),
        }
        for row in fetch_all(connection, sql, params)
    ]
