# Data Quality API

FastAPI service for the Data Quality book. Technology Risk stays in the React mock.

From this folder, with `backend/.env` present and not committed:

```text
docker compose up --build
```

The API listens on port 8080. React stays on Vite at port 5173. The image is not pushed.

Health:

- `GET /api/v1/dq/health` does not open Snowflake.
- `GET /api/v1/dq/health/ready` opens one connection and closes it.

After a full reseed, pre-generate the seven Red and Amber summaries once:

```text
python -m app.jobs.refresh_summaries --scope at-risk
```

Run that from this folder so `backend/.env` is found. A second run skips controls that already have a valid summary. Force Refresh in the UI always calls the agent again.

A definition with no snapshot is HTTP 200. Its reading status is `insufficient_data` and `snapshotUnavailable` is true. The handover name for that state was `UNKNOWN`. The UI badge has no UNKNOWN status, so the API keeps `insufficient_data` and does not invent a pass rate, counts, or trend.

`pytest` does not write to Snowflake or call Cortex. Tests marked `live` run only when `RUN_LIVE_SNOWFLAKE_TESTS=1`.
