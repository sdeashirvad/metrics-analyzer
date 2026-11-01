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


def find_latest_completed(connection, settings: Settings, control_id: str, analysis_type: str) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT RUN_ID, CONTROL_DATA_VERSION, RESULT, GENERATED_AT
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
        WHERE CONTROL_ID = %(control_id)s
          AND ANALYSIS_TYPE = %(analysis_type)s
          AND STATUS = 'COMPLETED'
          AND RESULT IS NOT NULL
        ORDER BY GENERATED_AT DESC
        LIMIT 1
        """,
        {"control_id": control_id, "analysis_type": analysis_type},
    )
    if not row:
        return None
    result = row["RESULT"]
    if isinstance(result, str):
        result = json.loads(result)
    generated = row["GENERATED_AT"]
    return {
        "runId": row["RUN_ID"],
        "controlDataVersion": row["CONTROL_DATA_VERSION"],
        "result": result,
        "generatedAt": generated.isoformat() if isinstance(generated, datetime) else str(generated),
    }


def find_by_id(connection, settings: Settings, control_id: str, run_id: str) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT RUN_ID, CONTROL_ID, ANALYSIS_TYPE, CONTROL_DATA_VERSION, DATASET_VERSION,
               PROMPT_VERSION, CALCULATION_VERSION, MODEL, STATUS, RESULT, ERROR_TEXT, GENERATED_AT
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
        WHERE CONTROL_ID = %(control_id)s
          AND RUN_ID = %(run_id)s
        """,
        {"control_id": control_id, "run_id": run_id},
    )
    return _pack(row) if row else None


def find_open_running(
    connection,
    settings: Settings,
    control_id: str,
    analysis_type: str,
    prompt_version: str,
    calculation_version: str,
    model: str,
    control_data_version: int,
) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT run.RUN_ID, run.CONTROL_ID, run.ANALYSIS_TYPE, run.CONTROL_DATA_VERSION,
               run.DATASET_VERSION, run.PROMPT_VERSION, run.CALCULATION_VERSION, run.MODEL,
               run.STATUS, run.RESULT, run.ERROR_TEXT, run.GENERATED_AT
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")} run
        WHERE run.CONTROL_ID = %(control_id)s
          AND run.ANALYSIS_TYPE = %(analysis_type)s
          AND run.PROMPT_VERSION = %(prompt_version)s
          AND run.CALCULATION_VERSION = %(calculation_version)s
          AND run.MODEL = %(model)s
          AND run.CONTROL_DATA_VERSION = %(control_data_version)s
          AND run.STATUS = 'RUNNING'
          AND NOT EXISTS (
            SELECT 1
            FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")} done
            WHERE done.STATUS = 'COMPLETED'
              AND done.RESULT:operationId::STRING = run.RUN_ID
          )
          AND NOT EXISTS (
            SELECT 1
            FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")} done
            WHERE done.STATUS = 'FAILED'
              AND STARTSWITH(done.ERROR_TEXT, 'op:' || run.RUN_ID || ' ')
          )
        ORDER BY run.GENERATED_AT DESC
        LIMIT 1
        """,
        {
            "control_id": control_id,
            "analysis_type": analysis_type,
            "prompt_version": prompt_version,
            "calculation_version": calculation_version,
            "model": model,
            "control_data_version": control_data_version,
        },
    )
    return _pack(row) if row else None


def find_terminal_for(connection, settings: Settings, operation_id: str) -> dict | None:
    row = fetch_one(
        connection,
        f"""
        SELECT RUN_ID, CONTROL_ID, ANALYSIS_TYPE, CONTROL_DATA_VERSION, DATASET_VERSION,
               PROMPT_VERSION, CALCULATION_VERSION, MODEL, STATUS, RESULT, ERROR_TEXT, GENERATED_AT
        FROM {settings.qualified("DQ_AI_ANALYSIS_RUNS")}
        WHERE (
            STATUS = 'COMPLETED'
            AND RESULT:operationId::STRING = %(operation_id)s
          ) OR (
            STATUS = 'FAILED'
            AND STARTSWITH(ERROR_TEXT, %(prefix)s)
          )
        ORDER BY CASE WHEN STATUS = 'COMPLETED' THEN 0 ELSE 1 END, GENERATED_AT
        LIMIT 1
        """,
        {"operation_id": operation_id, "prefix": f"op:{operation_id} "},
    )
    return _pack(row) if row else None


def _pack(row: dict) -> dict:
    result = row["RESULT"]
    if isinstance(result, str):
        result = json.loads(result)
    generated = row["GENERATED_AT"]
    return {
        "runId": row["RUN_ID"],
        "controlId": row["CONTROL_ID"],
        "analysisType": row["ANALYSIS_TYPE"],
        "controlDataVersion": row["CONTROL_DATA_VERSION"],
        "datasetVersion": row["DATASET_VERSION"],
        "promptVersion": row["PROMPT_VERSION"],
        "calculationVersion": row["CALCULATION_VERSION"],
        "model": row["MODEL"],
        "status": row["STATUS"],
        "result": result,
        "errorText": row["ERROR_TEXT"],
        "generatedAt": generated.isoformat() if isinstance(generated, datetime) else str(generated),
        "generatedAtValue": generated if isinstance(generated, datetime) else datetime.now(datetime.UTC),
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
