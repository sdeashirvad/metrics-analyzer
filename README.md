# Metrics Analyzer

Metric Intelligence Platform for two books, kept separate.

- **Data Quality** is read live from Snowflake. An investigation is drafted by a Snowflake Cortex Agent, checked against the retrieved facts, and stored so the next open can return the saved result.
- **Technology Risk** is illustrative scenario data served by the same API. It is not live Snowflake telemetry, and SMARTS is not connected.

The React application is in `frontend/`. The API is a FastAPI service in `backend/`. Snowflake scripts are in `snowflake/`.

## Screens

| Path | Screen |
| --- | --- |
| `/dashboard` | Portfolio health for both books |
| `/overview` | Triage |
| `/metrics` | Metric register |
| `/metrics/:id` | Metric or control detail |
| `/investigations/:id` | Investigation |
| `/architecture` | POC and proposed design |
| `/glossary` | Terms and conventions |

`/` redirects to `/dashboard`.

On the register, triage, dashboard, and detail pages, every row uses the same controls. **Investigation** is a status (Ready, Not run, Running, Not available, or Checking). **Open** retrieves a saved or seeded investigation. **Run** starts a live Data Quality investigation. **Detail** always opens the metric. Technology Risk can be opened only where a scenario investigation was seeded.

## Run the UI locally

```bash
cd frontend
npm ci
npm run dev
```

Vite serves `http://127.0.0.1:5173`. Set `VITE_API_BASE_URL` in `frontend/.env.development` to the API base, including `/api/v1`. The production build reads the same name from the environment at build time. `npm test` runs the Vitest checks. `npm run build` typechecks and writes `frontend/dist/`.

## Run the API locally

From `backend/`, with `backend/.env` present and not committed:

```bash
docker compose up --build
```

The API listens on port 8080. See [backend/README.md](backend/README.md) for health checks, investigation jobs, and tests. `CORS_ORIGINS` must include the UI origin.

## Cloudflare Pages

Set these in the Pages project, not in the repository:

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| `VITE_API_BASE_URL` | `https://metrics-analyzer-backend.sdeashirvad.com/api/v1` |

The variable is required for Production. Vite inlines it during the build, so save it before retrying a deployment. The API `CORS_ORIGINS` must include the Pages origin.

## Snowflake

The Data Quality tables, seeds, and semantic view are in [snowflake/README.md](snowflake/README.md). The API reads that database. It does not load the workbook from the browser.
