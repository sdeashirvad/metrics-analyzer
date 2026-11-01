from app.config import Settings
from app.db.connection import fetch_all
from app.db.rows import iso, rag


def notes(connection, settings: Settings, control_id: str) -> dict:
    events = fetch_all(
        connection,
        f"""
        SELECT EVENT_ID, EVENT_DATE, EVENT_TYPE, DESK_IDS, DESCRIPTION
        FROM {settings.qualified("CHANGE_INCIDENT_EVENTS")}
        WHERE RELATED_CONTROL_ID = %(control_id)s
        ORDER BY EVENT_DATE, EVENT_ID
        """,
        {"control_id": control_id},
    )
    commentary = fetch_all(
        connection,
        f"""
        SELECT COMMENTARY_DATE, RAG_AT_TIME, ANALYST_COMMENTARY, ROOT_CAUSE_CATEGORY, PATH_TO_GREEN, AUTHOR_ROLE
        FROM {settings.qualified("ANALYST_COMMENTARY")}
        WHERE CONTROL_ID = %(control_id)s
        ORDER BY COMMENTARY_DATE
        """,
        {"control_id": control_id},
    )
    return {
        "events": [
            {
                "id": row["EVENT_ID"],
                "date": iso(row["EVENT_DATE"]),
                "type": row["EVENT_TYPE"],
                "deskIds": row["DESK_IDS"],
                "description": row["DESCRIPTION"],
            }
            for row in events
        ],
        "commentary": [
            {
                "date": iso(row["COMMENTARY_DATE"]),
                "ragAtTime": rag(row["RAG_AT_TIME"]),
                "text": row["ANALYST_COMMENTARY"],
                "cause": row["ROOT_CAUSE_CATEGORY"],
                "path": row["PATH_TO_GREEN"],
                "author": row["AUTHOR_ROLE"],
            }
            for row in commentary
        ],
    }
