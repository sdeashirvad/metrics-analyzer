import json
import uuid
from datetime import datetime

from app.config import Settings
from app.db.connection import fetch_one


def find_completed(
    connection,
    settings: Settings,
    control_id: str,
    analysis_type: str,
    prompt_version: str,
) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT run.RUN_ID, run.RESULT, run.GENERATED_AT
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")} run
        JOIN {settings.qualified("DQ_CONTROL_SNAPSHOT")} snapshot
          ON snapshot.CONTROL_ID = run.CONTROL_ID
         AND snapshot.CONTROL_DATA_VERSION = run.CONTROL_DATA_VERSION
        WHERE run.CONTROL_ID = %(control_id)s
          AND run.ANALYSIS_TYPE = %(analysis_type)s
          AND run.PROMPT_VERSION = %(prompt_version)s
          AND run.CALCULATION_VERSION = snapshot.CALCULATION_VERSION
          AND run.MODEL = %(model)s
          AND run.STATUS = 'COMPLETED'
          AND run.RESULT IS NOT NULL
        ORDER BY run.GENERATED_AT DESC
        LIMIT 1
        """,
        {
            "control_id": control_id,
            "analysis_type": analysis_type,
            "prompt_version": prompt_version,
            "model": settings.model_identity,
        },
    )
    if not row:
        return None
    result = row["RESULT"]
    if isinstance(result, str):
        result = json.loads(result)
    generated = row["GENERATED_AT"]
    return {
        "runId": row["RUN_ID"],
        "result": result,
        "generatedAt": generated.isoformat() if isinstance(generated, datetime) else str(generated),
    }


def insert_run(
    connection,
    settings: Settings,
    *,
    control_id: str,
    analysis_type: str,
    control_data_version: int,
    dataset_version: int,
    prompt_version: str,
    calculation_version: str,
    status: str,
    result: dict | None,
    error_text: str | None,
) -> str:
    run_id = str(uuid.uuid4())
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""
            INSERT INTO {settings.qualified("DQ_AI_ANALYSIS_RUNS")} (
              RUN_ID, CONTROL_ID, ANALYSIS_TYPE, CONTROL_DATA_VERSION, DATASET_VERSION,
              PROMPT_VERSION, CALCULATION_VERSION, MODEL, STATUS, RESULT, ERROR_TEXT, GENERATED_AT
            )
            SELECT
              %(run_id)s, %(control_id)s, %(analysis_type)s, %(control_data_version)s, %(dataset_version)s,
              %(prompt_version)s, %(calculation_version)s, %(model)s, %(status)s,
              PARSE_JSON(%(result)s), %(error_text)s, CURRENT_TIMESTAMP()
            """,
            {
                "run_id": run_id,
                "control_id": control_id,
                "analysis_type": analysis_type,
                "control_data_version": control_data_version,
                "dataset_version": dataset_version,
                "prompt_version": prompt_version,
                "calculation_version": calculation_version,
                "model": settings.model_identity,
                "status": status,
                "result": None if result is None else json.dumps(result),
                "error_text": (error_text or None) and (error_text or "")[:2000],
            },
        )
        connection.commit()
    finally:
        cursor.close()
    return run_id
