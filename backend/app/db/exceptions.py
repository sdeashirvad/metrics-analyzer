from app.config import Settings
from app.db.connection import fetch_all, fetch_one
from app.db.rows import iso


def page(
    connection,
    settings: Settings,
    control_id: str,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    params: dict = {"control_id": control_id, "limit": page_size, "offset": (page - 1) * page_size}
    count_where = "WHERE CONTROL_ID = %(control_id)s"
    list_where = "WHERE exception.CONTROL_ID = %(control_id)s"
    if status:
        params["status"] = status
        count_where += " AND STATUS = %(status)s"
        list_where += " AND exception.STATUS = %(status)s"
    table = settings.qualified("DQ_EXCEPTIONS")
    desks = settings.qualified("DESK_HIERARCHY")
    total = fetch_one(connection, f"SELECT COUNT(*) AS N FROM {table} {count_where}", params)
    rows = fetch_all(
        connection,
        f"""
        SELECT
          exception.EXCEPTION_ID, exception.EXCEPTION_DATE, exception.CONTROL_ID,
          exception.DESK_ID, hierarchy.DESK_NAME, exception.TRADE_ID, exception.FIELD_NAME,
          exception.OFFENDING_VALUE, exception.FAILURE_REASON, exception.SEVERITY,
          exception.STATUS, exception.AGEING_DAYS, exception.ASSIGNED_TEAM
        FROM {table} exception
        LEFT JOIN {desks} hierarchy ON hierarchy.DESK_ID = exception.DESK_ID
        {list_where}
        ORDER BY exception.EXCEPTION_DATE DESC, exception.EXCEPTION_ID
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    statuses = fetch_all(
        connection,
        f"""
        SELECT DISTINCT STATUS FROM {table}
        WHERE CONTROL_ID = %(control_id)s
        ORDER BY STATUS
        """,
        {"control_id": control_id},
    )
    return {
        "total": int(total["N"]) if total else 0,
        "page": page,
        "pageSize": page_size,
        "statuses": [row["STATUS"] for row in statuses],
        "items": [
            {
                "id": row["EXCEPTION_ID"],
                "date": iso(row["EXCEPTION_DATE"]),
                "controlId": row["CONTROL_ID"],
                "deskId": row["DESK_ID"],
                "deskName": row["DESK_NAME"] or row["DESK_ID"],
                "tradeId": row["TRADE_ID"],
                "field": row["FIELD_NAME"],
                "value": row["OFFENDING_VALUE"],
                "reason": row["FAILURE_REASON"],
                "severity": row["SEVERITY"],
                "status": row["STATUS"],
                "ageingDays": int(row["AGEING_DAYS"]),
                "team": row["ASSIGNED_TEAM"],
            }
            for row in rows
        ],
    }
