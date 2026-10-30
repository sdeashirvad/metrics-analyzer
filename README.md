# Metrics Analyzer

Metric Intelligence Platform. The React application lives in `frontend/`. It is a demonstration: screens call an in-app mock, not SMARTS, Snowflake, or Cortex. Readings are illustrative unless a scenario fact says otherwise.

`backend/` is reserved for a future Spring Boot service. The mock API, contracts, and fixtures stay in `frontend/src/backend/`.

Shared data scripts stay at the repository root. `scripts/build-dq-fixtures.py` reads `SMARTS_DQ_mock_data.xlsx` from this directory when it is present, and otherwise from the parent directory. It writes JSON into `frontend/src/backend/data/dq/`.

```bash
cd frontend
npm ci
npm run dev
```

`npm run build` typechecks and writes `frontend/dist/`.

`/` opens the Dashboard. `/overview` is Triage. `/metrics` is the register.

Cloudflare Pages, set in the project dashboard:

- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Build output directory: `dist`
