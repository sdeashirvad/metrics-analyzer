from app.config import Settings
from app.db.connection import fetch_all
from app.db.rows import as_float, iso, rag


def desks(connection, settings: Settings, control_id: str, metric_date: str | None) -> list[dict]:
    date_filter = "AND desk.METRIC_DATE = %(metric_date)s" if metric_date else ""
    if not metric_date:
        date_filter = """
          AND desk.METRIC_DATE = (
            SELECT MAX(METRIC_DATE) FROM {desk_table} WHERE CONTROL_ID = %(control_id)s
          )
        """.format(desk_table=settings.qualified("DQ_RESULTS_BY_DESK"))
    sql = f"""
        SELECT
          desk.DESK_ID,
          hierarchy.DESK_NAME,
          hierarchy.BUSINESS_LINE,
          hierarchy.PRIMARY_REGION,
          desk.METRIC_DATE,
          desk.FAILED_RECORDS,
          desk.TOTAL_RECORDS,
          desk.PASS_RATE_PCT,
          desk.RAG_STATUS
        FROM {settings.qualified("DQ_RESULTS_BY_DESK")} desk
        JOIN {settings.qualified("DESK_HIERARCHY")} hierarchy
          ON hierarchy.DESK_ID = desk.DESK_ID
        WHERE desk.CONTROL_ID = %(control_id)s
        {date_filter}
        ORDER BY desk.FAILED_RECORDS DESC, desk.DESK_ID
    """
    params = {"control_id": control_id}
    if metric_date:
        params["metric_date"] = metric_date
    rows = fetch_all(connection, sql, params)
    failed_sum = sum(int(row["FAILED_RECORDS"]) for row in rows) or 1
    return [
        {
            "deskId": row["DESK_ID"],
            "deskName": row["DESK_NAME"],
            "line": row["BUSINESS_LINE"],
            "region": row["PRIMARY_REGION"],
            "date": iso(row["METRIC_DATE"]),
            "failed": int(row["FAILED_RECORDS"]),
            "total": int(row["TOTAL_RECORDS"]),
            "passRate": as_float(row["PASS_RATE_PCT"]),
            "status": rag(row["RAG_STATUS"]),
            "shareOfFailures": round(100 * int(row["FAILED_RECORDS"]) / failed_sum, 1),
        }
        for row in rows
    ]


def hotspots(connection, settings: Settings) -> list[dict]:
    sql = f"""
        WITH latest AS (
          SELECT MAX(METRIC_DATE) AS METRIC_DATE FROM {settings.qualified("DQ_RESULTS_BY_DESK")}
        )
        SELECT
          desk.DESK_ID,
          hierarchy.DESK_NAME,
          latest.METRIC_DATE,
          SUM(desk.FAILED_RECORDS) AS FAILED_RECORDS,
          SUM(desk.TOTAL_RECORDS) AS TOTAL_RECORDS
        FROM {settings.qualified("DQ_RESULTS_BY_DESK")} desk
        JOIN latest ON desk.METRIC_DATE = latest.METRIC_DATE
        JOIN {settings.qualified("DESK_HIERARCHY")} hierarchy
          ON hierarchy.DESK_ID = desk.DESK_ID
        GROUP BY desk.DESK_ID, hierarchy.DESK_NAME, latest.METRIC_DATE
        ORDER BY FAILED_RECORDS DESC, desk.DESK_ID
    """
    items = []
    for row in fetch_all(connection, sql):
        failed = int(row["FAILED_RECORDS"])
        total = int(row["TOTAL_RECORDS"])
        items.append(
            {
                "deskId": row["DESK_ID"],
                "deskName": row["DESK_NAME"],
                "failed": failed,
                "total": total,
                "passRate": round(100 * (total - failed) / total, 4) if total else None,
                "date": iso(row["METRIC_DATE"]),
                "basis": "Sum of failed and total records on the latest desk date. Not a lowest-pass-rate ranking.",
            }
        )
    return items
