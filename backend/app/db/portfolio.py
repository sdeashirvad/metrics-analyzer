from app.config import Settings
from app.db.connection import fetch_all, fetch_one
from app.db.rows import iso


def dataset(connection, settings: Settings) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT ACTIVE_DATASET_VERSION, SOURCE_LABEL, METRIC_DATE_MIN, METRIC_DATE_MAX,
               DEFINITION_ROWS, RESULT_ROWS
        FROM {settings.qualified("DQ_DATASET_STATE")}
        WHERE STATE_ID = 1
        """,
    )
    if not row:
        return None
    return {
        "datasetVersion": int(row["ACTIVE_DATASET_VERSION"]),
        "sourceLabel": row["SOURCE_LABEL"],
        "dateFrom": iso(row["METRIC_DATE_MIN"]),
        "dateTo": iso(row["METRIC_DATE_MAX"]),
        "definitionRows": int(row["DEFINITION_ROWS"]),
        "resultRows": int(row["RESULT_ROWS"]),
    }


def open_exception_count(connection, settings: Settings) -> int:
    row = fetch_one(
        connection,
        f"""
        SELECT COUNT(*) AS N FROM {settings.qualified("DQ_EXCEPTIONS")}
        WHERE STATUS = 'Open'
        """,
    )
    return int(row["N"]) if row else 0


def coverage(connection, settings: Settings) -> dict:
    desk_controls = fetch_one(
        connection,
        f"SELECT COUNT(DISTINCT CONTROL_ID) AS N FROM {settings.qualified('DQ_RESULTS_BY_DESK')}",
    )
    without_desk = fetch_one(
        connection,
        f"""
        SELECT COUNT(*) AS N FROM {settings.qualified("DQ_RESULTS")} result
        WHERE NOT EXISTS (
          SELECT 1 FROM {settings.qualified("DQ_RESULTS_BY_DESK")} desk
          WHERE desk.CONTROL_ID = result.CONTROL_ID
            AND desk.METRIC_DATE = result.METRIC_DATE
        )
        """,
    )
    without_story = fetch_one(
        connection,
        f"""
        SELECT COUNT(*) AS N FROM {settings.qualified("DQ_CONTROL_DEFINITIONS")}
        WHERE PLANTED_STORY IS NULL
        """,
    )
    return {
        "deskControls": int(desk_controls["N"]) if desk_controls else 0,
        "controlDatesWithoutDesk": int(without_desk["N"]) if without_desk else 0,
        "controlsWithoutNarrative": int(without_story["N"]) if without_story else 0,
    }


def desk_names(connection, settings: Settings) -> list[str]:
    rows = fetch_all(
        connection,
        f"SELECT DESK_NAME FROM {settings.qualified('DESK_HIERARCHY')} ORDER BY LENGTH(DESK_NAME) DESC",
    )
    return [row["DESK_NAME"] for row in rows]


def completed_investigation_ids(connection, settings: Settings) -> set[str]:
    rows = fetch_all(
        connection,
        f"""
        SELECT DISTINCT run.CONTROL_ID
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")} run
        JOIN {settings.qualified("DQ_CONTROL_SNAPSHOT")} snapshot
          ON snapshot.CONTROL_ID = run.CONTROL_ID
         AND snapshot.CONTROL_DATA_VERSION = run.CONTROL_DATA_VERSION
        WHERE run.ANALYSIS_TYPE = 'INVESTIGATION'
          AND run.STATUS = 'COMPLETED'
          AND run.RESULT IS NOT NULL
          AND run.MODEL = %(model)s
        """,
        {"model": settings.model_identity},
    )
    return {row["CONTROL_ID"] for row in rows}
