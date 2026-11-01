from app.config import Settings
from app.db.connection import fetch_all, fetch_one
from app.db.rows import as_float, as_int, iso, rag


def list_controls(connection, settings: Settings) -> list[dict]:
    sql = f"""
        SELECT
          definition.CONTROL_ID,
          definition.CONTROL_NAME,
          definition.DQ_DIMENSION,
          definition.FREQUENCY,
          definition.GREEN_THRESHOLD,
          definition.AMBER_THRESHOLD,
          definition.SEVERITY,
          definition.CHECK_LOGIC,
          definition.OWNER_ROLE,
          definition.REGULATION,
          definition.REGULATORY_REPORT,
          definition.CRITICAL_DATA_ELEMENT,
          definition.SOURCE_SYSTEM,
          definition.BCBS239_PRINCIPLE,
          definition.PLANTED_STORY,
          snapshot.CONTROL_DATA_VERSION,
          snapshot.PASS_RATE_PCT,
          snapshot.RAG_STATUS,
          snapshot.FAILED_RECORDS,
          snapshot.TOTAL_RECORDS,
          snapshot.AS_OF_DATE,
          snapshot.FIRST_RED_DATE,
          snapshot.LAST_RED_DATE,
          snapshot.POINT_COUNT,
          snapshot.HAS_DESK_SPLIT,
          snapshot.RECOVERED,
          snapshot.OPEN_EXCEPTION_COUNT,
          snapshot.EXCEPTION_COUNT,
          snapshot.OLDEST_OPEN_AGEING_DAYS,
          snapshot.EVENT_COUNT,
          snapshot.COMMENTARY_COUNT,
          snapshot.DATASET_VERSION,
          snapshot.CALCULATION_VERSION
        FROM {settings.qualified("DQ_CONTROL_DEFINITIONS")} definition
        LEFT JOIN {settings.qualified("DQ_CONTROL_SNAPSHOT")} snapshot
          ON snapshot.CONTROL_ID = definition.CONTROL_ID
        ORDER BY definition.CONTROL_ID
    """
    return [_control(row) for row in fetch_all(connection, sql)]


def get_control(connection, settings: Settings, control_id: str) -> dict | None:
    sql = f"""
        SELECT
          definition.CONTROL_ID,
          definition.CONTROL_NAME,
          definition.DQ_DIMENSION,
          definition.FREQUENCY,
          definition.GREEN_THRESHOLD,
          definition.AMBER_THRESHOLD,
          definition.SEVERITY,
          definition.CHECK_LOGIC,
          definition.OWNER_ROLE,
          definition.REGULATION,
          definition.REGULATORY_REPORT,
          definition.CRITICAL_DATA_ELEMENT,
          definition.SOURCE_SYSTEM,
          definition.BCBS239_PRINCIPLE,
          definition.PLANTED_STORY,
          snapshot.CONTROL_DATA_VERSION,
          snapshot.PASS_RATE_PCT,
          snapshot.RAG_STATUS,
          snapshot.FAILED_RECORDS,
          snapshot.TOTAL_RECORDS,
          snapshot.AS_OF_DATE,
          snapshot.FIRST_RED_DATE,
          snapshot.LAST_RED_DATE,
          snapshot.POINT_COUNT,
          snapshot.HAS_DESK_SPLIT,
          snapshot.RECOVERED,
          snapshot.OPEN_EXCEPTION_COUNT,
          snapshot.EXCEPTION_COUNT,
          snapshot.OLDEST_OPEN_AGEING_DAYS,
          snapshot.EVENT_COUNT,
          snapshot.COMMENTARY_COUNT,
          snapshot.DATASET_VERSION,
          snapshot.CALCULATION_VERSION
        FROM {settings.qualified("DQ_CONTROL_DEFINITIONS")} definition
        LEFT JOIN {settings.qualified("DQ_CONTROL_SNAPSHOT")} snapshot
          ON snapshot.CONTROL_ID = definition.CONTROL_ID
        WHERE definition.CONTROL_ID = %(control_id)s
    """
    row = fetch_one(connection, sql, {"control_id": control_id})
    return _control(row) if row else None


def _control(row: dict) -> dict:
    has_snapshot = row.get("RAG_STATUS") is not None or row.get("CONTROL_DATA_VERSION") is not None
    return {
        "id": row["CONTROL_ID"],
        "name": row["CONTROL_NAME"],
        "dimension": row["DQ_DIMENSION"],
        "frequency": row["FREQUENCY"],
        "green": as_float(row["GREEN_THRESHOLD"]),
        "amber": as_float(row["AMBER_THRESHOLD"]),
        "severity": row["SEVERITY"],
        "checkLogic": row["CHECK_LOGIC"],
        "owner": row["OWNER_ROLE"],
        "regulation": row["REGULATION"],
        "report": row["REGULATORY_REPORT"],
        "cde": row["CRITICAL_DATA_ELEMENT"],
        "sourceSystem": row["SOURCE_SYSTEM"],
        "principle": row["BCBS239_PRINCIPLE"],
        "plantedStory": row["PLANTED_STORY"],
        "snapshotUnavailable": not has_snapshot,
        "controlDataVersion": as_int(row.get("CONTROL_DATA_VERSION")),
        "datasetVersion": as_int(row.get("DATASET_VERSION")),
        "calculationVersion": row.get("CALCULATION_VERSION"),
        "passRate": as_float(row.get("PASS_RATE_PCT")),
        "status": rag(row.get("RAG_STATUS")) if has_snapshot else "insufficient_data",
        "failed": as_int(row.get("FAILED_RECORDS")),
        "total": as_int(row.get("TOTAL_RECORDS")),
        "asOf": iso(row.get("AS_OF_DATE")),
        "firstRed": iso(row.get("FIRST_RED_DATE")),
        "lastRed": iso(row.get("LAST_RED_DATE")),
        "pointCount": as_int(row.get("POINT_COUNT")),
        "hasDeskSplit": bool(row.get("HAS_DESK_SPLIT")) if has_snapshot else False,
        "recovered": bool(row.get("RECOVERED")) if has_snapshot else False,
        "openExceptions": as_int(row.get("OPEN_EXCEPTION_COUNT")),
        "exceptionCount": as_int(row.get("EXCEPTION_COUNT")),
        "oldestOpenAge": as_int(row.get("OLDEST_OPEN_AGEING_DAYS")),
        "eventCount": as_int(row.get("EVENT_COUNT")) or 0,
        "commentaryCount": as_int(row.get("COMMENTARY_COUNT")) or 0,
    }
