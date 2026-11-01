"""One-off summary refresh. Not a resident worker and not a Snowflake task."""

from __future__ import annotations

import argparse
import logging

from app.analysis.service import cached_analysis, run_analysis
from app.config import load_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.connection import connect
from app.db.controls import list_controls

logger = logging.getLogger(__name__)


def refresh_at_risk() -> dict:
    settings = load_settings()
    with connect(settings) as connection:
        controls = list_controls(connection, settings)
    targets = [item for item in controls if item["status"] in {"red", "amber"} and not item["snapshotUnavailable"]]
    created = 0
    skipped = 0
    failed = 0
    for control in targets:
        with connect(settings) as connection:
            if cached_analysis(connection, settings, control["id"], "SUMMARY"):
                skipped += 1
                continue
            try:
                run_analysis(connection, settings, control["id"], "SUMMARY", False)
                created += 1
            except AppError:
                failed += 1
                logger.info("summary refresh failed control=%s", control["id"])
    return {"scope": "at-risk", "selected": len(targets), "created": created, "skipped": skipped, "failed": failed}


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", required=True, choices=["at-risk"])
    parser.parse_args()
    result = refresh_at_risk()
    print(
        f"scope={result['scope']} selected={result['selected']} "
        f"created={result['created']} skipped={result['skipped']} failed={result['failed']}"
    )


if __name__ == "__main__":
    main()
