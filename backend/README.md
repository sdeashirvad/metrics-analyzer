# Metrics Analyzer API

FastAPI service. Data Quality comes from Snowflake. Technology Risk comes from the packaged scenario in `app/fallback_assets/`. The browser never queries Snowflake or Cortex.

Copy `backend/.env.example` to `backend/.env`. Do not commit `.env`.

| Variable | Role |
| --- | --- |
| `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD` | Snowflake login |
| `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE` | Database location. The scripts use database `METRICS_ANALYZER` and schema `DQ`. |
| `CORTEX_AGENT` | Published Cortex Agent used for Data Quality investigations and summaries |
| `CORS_ORIGINS` | Comma-separated UI origins. Include `http://localhost:5173`, `http://127.0.0.1:5173`, and the Cloudflare Pages origin. |

From this folder:

```text
docker compose up --build
```

The API listens on port 8080. The React app stays on Vite at port 5173. The image is not pushed from this repository.

## Health

- `GET /api/v1/dq/health` does not open Snowflake.
- `GET /api/v1/dq/health/ready` opens one connection and closes it.

## Books

Data Quality routes are under `/api/v1/dq/`. They serve the portfolio, a control, its trend, desks, exceptions, and notes.

Technology Risk routes are under `/api/v1/tr/`. They serve the scenario overview, register, metric, trend, organization contribution, and seeded investigations. A metric with no seeded investigation returns 404. These routes do not open Snowflake.

## Investigations

A saved investigation is a read. Starting one is a separate request.

- `GET /api/v1/dq/controls/{id}/analyses/investigation` returns 200 when a completed result is stored, and 404 when it is not. It does not start Cortex.
- `POST /api/v1/dq/controls/{id}/analyses` with `analysisType` and `forceRefresh` returns 202 and a `runId` when a run is accepted, or 200 when a cached result is returned.
- `GET /api/v1/dq/controls/{id}/analyses/operations/{runId}` is the status poll.

Two investigations can run at once. A third request is told to wait. Leaving the page does not cancel a run. A narrative is stored only when its control, dates, counts, and status match the facts that were retrieved. A rejected run does not replace a saved investigation.

A control with no snapshot is still HTTP 200 on the detail route. Its reading status is `insufficient_data` and `snapshotUnavailable` is true. The API does not invent a pass rate, counts, or trend.

## Summaries

After a full reseed, pre-generate the Red and Amber summaries once:

```text
python -m app.jobs.refresh_summaries --scope at-risk
```

Run that from this folder so `backend/.env` is found. A second run skips controls that already have a valid summary.

## Tests

`pytest` does not write to Snowflake or call Cortex. Tests marked `live` run only when `RUN_LIVE_SNOWFLAKE_TESTS=1`.
