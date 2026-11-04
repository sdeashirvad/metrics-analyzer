# Metrics Analyzer V2 — Implementation Plan

Companion to `API_CONTRACT.md` (contract version `2.0.0`). The contract is the source of truth. Where this plan names an endpoint, field, error code, limit or route, it means the one in the contract. Section numbers such as "contract 4.13" refer to that file. Decision ids (DEC-nn), assumption ids (A-n) and open items (OI-nn) are defined in the contract section 10 or below.

Evidence labels are the same as in the contract: **VERIFIED** (read from this repository, the deployed-object scripts and validation notes, the JSON extracts, or the source CSV), **PROPOSAL**, **ASSUMPTION**.

This is a planning document. No application, backend, Snowflake or deployment code was changed to write it. **Revision 2** removed every application database; conversations are Snowflake Cortex Agent threads (contract section 5). **Revision 3 (2026-11-04)** records the live thread tests: both agents create a thread from SQL, accept a background first message, continue on that thread, and keep the Data agent's SQL tool results in `THREAD_MESSAGES`. Building starts at B0. There is no spike left to run first.

---

## A. Repository baseline and preservation

### A.1 Baseline (VERIFIED)

Repository root `metrics-analyzer/`.

| Area | Facts |
| --- | --- |
| Frontend | React 19, `react-router-dom` 7, Vite 7, TypeScript 5.9 strict (`noUnusedLocals`, `noUnusedParameters`), Vitest 3. Scripts: `dev`, `build` (`tsc --noEmit && vite build`), `preview`, `test` (`vitest run`). No ESLint, no Prettier script, no component-test libraries, no Playwright. `vite.config.ts` has only the React plugin and port 5173 (default `base: '/'`, default Vitest environment). |
| Frontend routing | `src/App.tsx` builds the router at module scope with `createBrowserRouter` and no basename: index redirects to `/dashboard`; routes `dashboard`, `overview` (Triage), `metrics`, `architecture`, `glossary`, `metrics/:metricId`, `investigations/:metricId`, and `*`. `src/main.tsx` statically imports five global CSS files (`tokens`, `base`, `components`, `pages`, `architecture`) and renders `RouterProvider`. |
| Frontend links | No `<a href="/...">`, no `window.location`, no `pushState` use in `src` (grep). All internal links are router `Link`/`NavLink`/`navigate` with absolute `to` paths, so they follow a router basename. In-page `#anchor` links exist on the Glossary page and are unaffected. |
| Frontend state | `useUrlState` (query string), `useOrigin` (router location state and `history.state.idx`), module-level cache in `useQuery`, `sessionStorage` key prefix `ma-dq-run:`, `localStorage` keys in `state/analysisState.ts` and `state/etaStore.ts`. |
| Frontend API | `src/backend/services/httpApi.ts`: base from `VITE_API_BASE_URL` (value ends in `/api/v1`), 20 s timeout, one retry on GET, DQ investigation polling. |
| Frontend tests | 6 Vitest files, all pure TypeScript: `architecture/journey`, `investigation/access`, `investigation/openFlow`, `metric/summaryFlow`, `state/etaStore`, `state/analysisState`. |
| Public assets | `frontend/public/` contains only `favicon.svg`. No `_redirects`, `_routes.json` or `404.html`. `index.html` references `/favicon.svg` and `/src/main.tsx` with absolute paths. |
| Backend | FastAPI 0.115.6, Python 3.12 image, one uvicorn worker (`--workers 1`), port 8080, `mem_limit: 512m`, healthcheck on `/api/v1/dq/health/ready`. Routers: `dq`, `tr`. `main.py` registers CORS (`GET`, `POST`; `Content-Type`), an `AppError` handler and a catch-all 502. Snowflake connections are short-lived; deterministic reads use a 5 s deadline and a circuit gate with packaged-JSON fallback; investigation jobs run in daemon threads with a 2-slot capacity, state in `DQ_AI_ANALYSIS_RUNS`. |
| Backend tests | `pytest` (config `backend/pytest.ini`, marker `live`, enabled by `RUN_LIVE_SNOWFLAKE_TESTS=1`). Ten test modules under `backend/tests/` including `test_parser.py`, `test_fallback.py`, `test_config.py`, `test_investigation_jobs.py`. `httpx` is already a dependency, so FastAPI `TestClient` works. |
| Deployment | Frontend on Cloudflare Pages (root `frontend`, `npm run build`, output `dist`, `VITE_API_BASE_URL=https://metrics-analyzer-backend.sdeashirvad.com/api/v1`). Backend as a Docker image built from `backend/` (compose: no volume, no restart policy, container user uid 10001, `--workers 1`, `mem_limit: 512m`; VERIFIED in the repository). The VM's compose file, restart policy and Nginx configuration are **not in the repository and were not inspected**; that Nginx fronts the backend is stated in the project brief only (UNVERIFIED, gates V-1 to V-5, section I). The Pages origin `https://metrics-analyzer-poc.pages.dev` is documented in `docs/poc-url-inspection/README.md`. |
| Git state | The git root is `metrics-analyzer/`. Untracked items are classified in A.5; none is read, moved or deleted by this plan. |
| Authentication | None in `backend/app` (VERIFIED by reading `main.py` and every router): no guard, key, bearer or session. CORS is the only control and is not authentication. V2 adds signed handles and in-memory limits (contract 3.8). DEC-16: this demo adds no end-user login. |
| Snowflake account | Region `AWS_AP_SOUTH_1`, version `10.40.100`, connection role `ACCOUNTADMIN` (VERIFIED by one read-only probe on 2026-11-04). The backend's existing hard-coded `ACCOUNTADMIN` login on this temporary demo account is the accepted runtime identity for V2 (owner instruction; OI-01). |
| Agents | `DATA_AGENT_RUN(agent, body, TRUE)` with `"stream": false` is the existing call. On 2026-11-04 both V2 agents created a thread from that call with no `thread_id`, accepted `"background": true` on the first message and on follow-ups, and returned tool results through `THREAD_MESSAGES` (contract 5.5.2). The null `thread_id` values in `agent_golden_answers.json` are the old parser dropping an integer `metadata.thread_id`. Both live specifications still hard-code `2026-10-31`, and Agent 2 still forbids a `SUM/SUM` rate; specification v2, generated in this plan and applied in step 10, replaces both. Contract examples that contain `2026-10-31` are October 2026 dataset values, not literals to copy into V2 code (AG-13). |

### A.2 What must not change

1. Legacy page behaviour, deep links, state handling, the Architecture visualisation and walkthrough, API integrations, loading, caching, retry and error behaviour, and the `VITE_API_BASE_URL` handling.
2. `/api/v1/dq/*`, `/api/v1/tr/*`, their response shapes, jobs, gates, fallback assets, `Settings` defaults and `app.db.connection`.
3. The Snowflake dataset, MCP servers, credentials, roles and grants. The only Snowflake changes V2 makes, both in the implementation phase after approval, are the agent specification update of C (`20_agent_definitions_update.sql`, DEC-17) and the one-off generation of precomputed investigation files (which creates agent threads). Nothing is created, altered or run in Snowflake while writing the plans.
4. The Cloudflare Pages project settings and the VM's proxy.

### A.3 Edits to existing files (the complete list)

| File | Edit | Why |
| --- | --- | --- |
| `frontend/src/main.tsx` | Replace the body with a small bootstrap that picks an entry module (A.4). The five CSS imports and the `RouterProvider` render move, unchanged, to a new `frontend/src/legacy-entry.tsx`. | Isolates legacy CSS and router from V2. |
| `frontend/src/App.tsx` | Add `{ basename: '/legacy' }` as the second argument of `createBrowserRouter` (one constant, one argument). Nothing else. | Mounts the legacy router under `/legacy`. |
| `backend/app/main.py` | One line: `register_v2(app)` (includes the two V2 routers and the start-up check). No CORS change. | Registers V2 routers (contract 1.3). |
| `frontend/package.json`, `package-lock.json` | Only if the component-test and E2E dev dependencies are approved (F.1). | Test tooling. |

Everything else is new files. There is **no** change to `docker-compose.yml`, `Dockerfile`, `requirements.txt`, CORS, environment variables, volumes or the VM. `frontend/src/components/AppShell.tsx` is not edited. An optional "Open the new app" link in the legacy shell is deliberately left out.

### A.4 Mounting the legacy app under `/legacy` (PROPOSAL, DEC-07)

**Bootstrap logic** (`main.tsx`, backed by a pure function `resolveEntry(location)` in `frontend/src/bootstrap/resolveEntry.ts`, unit-tested):

| Condition on `window.location.pathname` | Action |
| --- | --- |
| equals `/legacy` or starts with `/legacy/` | `import('./legacy-entry')` (legacy router, basename `/legacy`, five legacy CSS files) |
| matches `^/(dashboard|overview|metrics|investigations|glossary)(/|$)` | `window.location.replace('/legacy' + pathname + search + hash)`; nothing renders in between |
| anything else | `import('./v2/entry')` (V2 router, V2 CSS) |

`/architecture` is intentionally not redirected: from this release it is the V2 Architecture page. The legacy copy is at `/legacy/architecture`.

**Why this shape.**

- The legacy modules keep every absolute `to="/dashboard"`-style link. With basename `/legacy`, React Router prefixes them, so a click on "Metrics" lands on `/legacy/metrics`. `useLocation().pathname` inside legacy code excludes the basename, so `useOrigin`, `useBackTarget` and `useUrlState` behave as before (VERIFIED by reading them).
- Global, unprefixed class names (`.app`, `.sidebar`, `.card`) exist in both the legacy CSS and the prototype CSS. They must never load together. A page load runs exactly one entry; legacy and V2 are separate dynamic chunks with separate CSS; moving between apps is a normal link (`<a href>`) that causes a full page load, never a client-side route change.
- Vite `base` stays `/`, so built assets are `/assets/...` and resolve from any URL depth.

**Cases the plan must cover (each has an acceptance test in F.2):**

| Case | Behaviour |
| --- | --- |
| Direct navigation to `/legacy/...` | Cloudflare Pages returns `index.html`; the bootstrap loads the legacy chunk; the legacy router renders the page. |
| Refresh of nested routes (`/legacy/metrics/DQ-001`, `/legacy/investigations/DQ-001`) | Same as above; deep state in `?query` is preserved. |
| `/legacy` and `/legacy/` | Legacy index route redirects to `/dashboard`, which the basename turns into `/legacy/dashboard`. |
| SPA fallback | Cloudflare Pages serves `index.html` for unknown paths when no top-level `404.html` exists (A-6); `frontend/public` has none and none is to be added. If the Pages preview shows otherwise, add `public/_redirects` containing exactly `/* /index.html 200` and re-test. No other redirect file is added. |
| Assets and static paths | `/assets/*` and `/favicon.svg` are absolute; they load under `/legacy/...` too. A check on `dist/index.html` confirms every `href`/`src` starts with `/`, with no relative paths and no `<base>`. |
| Query strings | `useSearchParams` is basename-independent. The legacy-alias redirect carries `search`. |
| Hash | The app uses browser routing, not hash routing. In-page anchors such as `#gloss-ids` resolve against the current `/legacy/glossary` URL. The alias redirect carries `hash`. |
| Old bookmarks | `/dashboard`, `/overview`, `/metrics`, `/metrics/<id>`, `/investigations/<id>`, `/glossary` redirect to `/legacy/...` with query and hash. `/` was `/dashboard` and is now the V2 Dashboard (documented change). `/architecture` is V2. |
| Unknown legacy paths | The legacy `*` route renders the legacy NotFound inside `/legacy`. |
| Unknown V2 paths | The V2 `*` route renders a V2 NotFound. |
| Cloudflare Pages routing | No `_routes.json` or Functions are used (none exist). Preview and production deployments need no setting change. |
| Dev server | Vite's default SPA fallback serves `index.html` for `/legacy/...`; `npm run dev` and `npm run preview` both work. |

### A.5 Baseline preservation and untracked work (NEW, step B0)

Nothing in this plan may delete, reset, clean, stash or overwrite existing work. The repository holds substantial untracked material that exists nowhere else.

**Classification (VERIFIED by listing; contents of `METRICSanalyzer1@` deliberately not displayed).**

| Item | What it is | Class | Treatment |
| --- | --- | --- | --- |
| `docs/poc-url-inspection/` | Evidence screenshots and README of the POC URL inspection | Evidence | Retain. Commit later if the owner wants it in history |
| `resources/.../mock_data_deployment_v1/` | The supplied input package for the dataset | Supplied input, read-only | Retain, never edit |
| `resources/metrics_analyzer_v2/` | `API_CONTRACT.md` and `IMPLEMENTATION_PLAN.md` | Planning documents (these) | Retain; commit with the V2 work |
| `snowflake/mock_data_setup/` | Executed scripts, exports, validation notes, golden answers | Critical: the only record of what was built in Snowflake and the source of fixtures | Retain; backed up in B0; new V2 scripts go beside it |
| `snowflake_v1.zip` to `snowflake_v4.zip` | Superseded bundles of tracked Snowflake scripts | Superseded copies | Retain; no action |
| `frontend/.env.production` | 75 bytes; matches a single public `VITE_API_BASE_URL` line | Public configuration | Retain; owner confirms it holds no secret before any commit |
| `METRICSanalyzer1@` | 59 bytes, one line, no whitespace, created 2 Nov 02:17, referenced by nothing | Unknown: possibly sensitive | Do **not** commit and do **not** remove. Treat as sensitive. The owner reviews it, then moves or deletes it. The plan never reads or prints it |

**Step B0 (before any file is created or edited).**

1. Record `git rev-parse HEAD` and `git status --porcelain` into `resources/metrics_analyzer_v2/baseline/BASELINE.txt` (the folder is itself untracked and new).
2. Archive the untracked set (every item above, including `METRICSanalyzer1@`) into a zip **outside the repository**, for example `C:\Users\aashirvad\Documents\ControlLens-baseline\untracked-<date>.zip`, with a SHA-256 manifest of every file. The archive is read-only afterwards. Protect it like the original because it may contain the unknown file.
3. Work on a new branch created from the current `HEAD`. Do not commit until the owner asks.
4. Forbidden commands during implementation: `git clean` (any flags), `git reset --hard`, `git checkout -- .`, `git restore .`, `git stash -u` and `git stash --include-untracked`, `git rebase` over untracked files, `rm -rf` on repository folders, and any bulk delete.
5. At the end of implementation, recompute the manifest over the working tree and compare it with the archive. Any difference in an untracked path is investigated before release.

---

## B. Frontend target architecture

### B.1 Directory layout (all new, under `frontend/src/`)

```
bootstrap/resolveEntry.ts          # pure routing decision for main.tsx
legacy-entry.tsx                   # moved body of the old main.tsx
v2/
  entry.tsx                        # imports V2 CSS, renders RouterProvider
  routes.tsx                       # V2 route table (single owner)
  shell/V2Shell.tsx                # sidebar, env bar, outlet
  styles/{tokens,base,components,pages,architecture}.css   # ported from the design file
  api/{config,http,types,portfolio,agents}.ts
  hooks/{useApiQuery,useScopeFilters,useAgentRun,usePolling}.ts
  agent/{conversationStore,contextClient,errors}.ts       # the only readers and writers of ma2:* keys
  components/                      # primitives (see B.3)
  features/
    dashboard/                     # DashboardPage and cards
    register/                      # RegisterPage, MetricTable, PreviewDrawer
    metric/                        # MetricSummaryPage and sections
    investigation/                 # MetricInvestigationPage, ApplicationInvestigationPage
    agent/                         # AgentHome, ConversationPage, ContextReview, AgentPicker, DatasetView, AnalysisView, Composer
    architecture/                  # copied from legacy and revised (B.5)
    definitions/                   # DefinitionsPage
  __fixtures__/                    # contract fixtures built from the REAL examples
```

### B.2 Route table, state owners, API dependencies

| Route | Page and main components | State owner | API |
| --- | --- | --- | --- |
| `/` | `DashboardPage`: `ScopeFilterBar`, `KpiTiles`, `CoverageStrip`, `ComplianceDistribution`, `TestingCard`, `RiskDistribution`, `MovementTrendCard`, `OrgContributionCard`, `AttentionCard` (tabs: Non-compliant, No completed test, Failed test, Newly non-compliant, Resolved), `DataCoverageCard` | URL query (`month`, filters, `attention`, `orgTree`, `level`); each card owns its query status | `filters`, `overview`, `trends`, `distributions/*`, `org/contribution`, `data-coverage`, `applications` |
| `/register` | `RegisterPage`: `ScopeFilterBar`, search box, `MetricTable` (sort, pager, sparkline), `PreviewDrawer` | URL (`q`, `sort`, `page`, `pageSize`, filters, `preview`); drawer open state derives from `preview` | `filters`, `metrics`, `metrics/{id}/preview` |
| `/register/:metricId` | `MetricSummaryPage`: `MetricHeader`, `DefinitionCalculation`, `RateKpis`, `TrendChart` (with composition), `DistributionTabs`, `BreakdownTable`, `ContributorsTable`, `ProvisionalPanel`, actions (Open Investigation, Chat with Agent) | URL (`month`, filters, `tab`, `breakdown`) | `metrics/{id}`, `/trend`, `/breakdowns`, `/applications` |
| `/investigate/metrics/:metricId` | `MetricInvestigationPage`: `ObservationsSection`, `DerivedSection` (change, composition, contributors), `SourceRows`, `AgentExplanationPanel`, `Breadcrumbs` (Register / metric) | URL (`month`, filters); `AgentExplanationPanel` reads `agentAnalysis` | `investigations/metrics/{id}`, `/trend`, `/breakdowns`, `/applications` |
| `/investigate/applications/:eonId` | `ApplicationInvestigationPage`: `ApplicationHeader`, `StatusHistoryStrip` (hatched unobserved), `MetricRowsTable`, `AttributesRail`, `OwnersToggle`, `PeersCard`, `AgentExplanationPanel` | URL (`month`, `metric`, `owners`) | `investigations/applications/{eonId}` |
| `/agent` | `AgentHome`: `AgentPicker` (two cards), recent conversations from this browser | `localStorage` (`ma2:conversations`, written only by `agent/conversationStore.ts`) | `agents` |
| `/agent/:agentKey` | `NewConversationPage`: default portfolio context chips, `ContextReview`, `Composer` | local component state for the review; the reviewed `ContextRequest` and `contextHash` in memory and `sessionStorage` | `agents/context/preview`, `agents/conversations` |
| `/agent/:agentKey/:conversationId` | `ConversationPage`: `MessageList`, `AnalysisView` or `DatasetView`, `RunStatus` (events, elapsed, overdue notice, Stop waiting, retry), `GroundingRail` (read-only), `Composer` | the Snowflake thread via the backend plus `useAgentRun` polling; the URL carries the conversation handle | `agents/conversations/{handle}`, `.../context`, `.../messages`, `agents/runs/*`, export link |
| `/architecture` | `ArchitecturePage` (B.5) | URL `tab` | none |
| `/definitions` | `DefinitionsPage` with `#PD-xx` anchors | none | `definitions` |
| `*` | `NotFoundPage` | none | none |

Contextual entry points reuse one component, `ChatWithAgentButton`, that takes `{ entrySurface, scope, filters }`, opens `ContextReviewDialog` (preview call, item switches, exact-text disclosure), then `AgentPicker` (two cards, no default selected), then creates the conversation and navigates to `/agent/:agentKey/:conversationId`. There is no auto-routing.

Sidebar items: Dashboard, Metric register, Agent (with recent conversations when on an agent route), Architecture; utility link "Definitions & conventions" to `/definitions`. There is no Triage item.

### B.3 Components and visuals (no chart dependency)

The prototype draws with inline SVG. V2 keeps that: `Sparkline`, `LineChart`, `StackedBar`, `BarList`, `StatusStrip` (month cells, hatched when not observed) are small SVG components with unit tests on their pure scale and layout functions. No chart library is added (DEC-13). Other primitives: `Chip` (with Provisional / Assumption / Not available variants linked to `/definitions#PD-xx`), `Card`, `SectionState` (loading, empty, error, retry), `Pager`, `SelectField`, `Drawer`, `Dialog`, `CodeBlock` (read-only SQL), `ResultsTable`, `Tabs`, `Breadcrumbs`.

### B.4 Triage removal, applied to V2

- No Triage page, route, nav item, breadcrumb or link in `v2/`. A repository-wide grep for `Triage`, `overview` routes and "Back to Triage" inside `frontend/src/v2/` is part of acceptance (F.2, N-2).
- Folded content: attention indicators and non-compliant application summaries become `AttentionCard` on the Dashboard (tabs backed by `GET /portfolio/applications?attention=...`, grouped counts from `summary.byOrgLevel1`, each row opens `/investigate/applications/:eonId`); movement becomes the movement strip in `KpiTiles` plus the trend card; organisational hotspots become `OrgContributionCard` (non-compliant share labelled Provisional, with the denominator shown); register-style filtering uses `ScopeFilterBar` and the Register's `hasNonCompliant` filter. The legacy Triage remains at `/legacy/overview`.
- "Open more in Triage" becomes "View all N" in the attention card, which pages the same list in place (`pageSize` 10 to 100). "Back to Triage" becomes "Back" via a V2 `useBackTarget` (own copy of the origin-state pattern) that falls back to `/`.

### B.5 Architecture page in V2 (PROPOSAL)

Legacy reuse without a CSS clash: copy, do not import.

- Copy `features/architecture/{ArchitecturePage,ArchitectureDiagram,DetailPanel,Walkthrough}.tsx`, `journey.ts`, `journey.test.ts`, `model.ts` and `styles/architecture.css` to `v2/features/architecture/`, together with the three small primitives they use (`PageHeader`, `ProvenanceChip`, `Tabs`) and `useUrlState`. The legacy files stay as they are at `/legacy/architecture`.
- Re-point the CSS to V2 tokens. Revise `model.ts` text: remove the "Triage" mentions (lines 99 and 112 name it) and add the V2 pieces: Portfolio API, agent gateway, Snowflake Cortex Agent threads (the conversation store), the two agents, the `MOCK_DATA` schema and semantic view, and the backend's existing Snowflake login. The journey test is adapted to the revised graph. Anything described as running must be true; planned pieces carry the existing "proposed" status marker.
- Effort: medium. The risk is visual regression from token differences, mitigated by a manual side-by-side check.

### B.6 Design source and fidelity

The design reference is the attached `Metrics Analyzer proposed design.html` (a bundled single file outside the repository). All seven screens in the file were inspected: Dashboard, Triage (not carried), Register with the preview drawer, Metric detail, Application investigation, Analyst agent and Data agent. Architecture and Glossary are navigation items without a screen in the file. The prototype's Investigation screen is application-scoped only; the metric-scoped investigation is new in this plan. Implementation ports tokens and layout from it. Specific prototype content that is **not** carried because it is not real or not allowed: hard-coded figures, `fact_metric_observation` and other non-existent objects, "Metric_Family_NN" and "Variant A/B" labels, "Edit" and "Run again" on SQL, "Max 1,000 rows", credit figures, "Established" badges on agent text. Step S1 includes extracting the CSS and layout values from the file into `v2/styles/`; the file itself can optionally be copied to `resources/metrics_analyzer_v2/design/` for the team.

---

## C. Backend target architecture (REVISED)

All new code is under new packages; no existing module is edited except `main.py` (A.3). There is no database, no store package and no state file.

```
backend/app/
  portfolio/
    router.py            # /api/v1/portfolio/*, thin: parse, call service, wrap envelope
    models.py            # pydantic response models mirroring contract section 4
    filters.py           # ScopeFilters parser, allow-lists (from the filters endpoint), validation
    month.py             # resolve_month(scope.month): explicit month wins, else MAX(REPORTING_MONTHEND_DATE)
    repository.py        # the only module with SQL for Portfolio; bound params; grain-named functions
    services/            # overview, trends, distributions, org, coverage, applications, metrics, investigations
    definitions.py       # provisional definition registry PD-01..PD-19 and definitionsVersion (single owner)
    fallback.py          # reads app/fallback_assets/v2/*.json copies of the export extracts; maps columns
    cache.py             # TTL cache keyed by endpoint + params + dataset.promotedAt
  agents/
    router.py            # /api/v1/agents/*
    models.py            # pydantic models for contract sections 5 and 6 (extra = forbid on requests)
    registry.py          # agentKey -> Snowflake object name constants (the only place names appear)
    tokens.py            # HMAC-signed conversation handle and run token (stateless); key from the existing Snowflake credential, optional V2_SIGNING_KEY
    threads.py           # submit: DATA_AGENT_RUN with thread_id, parent_message_id, background; read: THREAD_MESSAGES, incremental
    runs.py              # derive run state from token + thread (RUNNING/COMPLETED/FAILED, overdue, late completion)
    conversations.py     # create (thread + first message), follow-up, get (read thread, parse), context-of-conversation
    context/{catalogue,builder,render}.py   # items per surface, readable lines, rendered text, hash; stateless
    parse.py             # tool-aware parser (contract 6.4); accepts THREAD_MESSAGES shapes
    export.py            # CSV export with formula-injection guard
    limits.py            # in-memory counters, poll coalescing, duplicate suppression, bounded caches
    precomputed.py       # serves backend/app/fallback_assets/v2/investigations/* (contract 6.7)
  common/
    v2_errors.py         # V2Error, error envelope, V2 route class with scoped validation handler
    v2_envelope.py       # meta builder: requestId, lineage, cache, source, dataset, definitionsVersion
backend/app/fallback_assets/v2/investigations/   # metrics/<id>.json, applications/<eon>.json, manifest.json (generated, reviewed)
backend/scripts/render_agent_spec.py             # renders both agent specs from definitions.py
backend/scripts/generate_precomputed_investigations.py
snowflake/mock_data_setup/sql/20_agent_definitions_update.sql   # ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION (generated; run once after approval)
```

Details:

- **Envelope and errors.** A custom `APIRoute` subclass used only by the two new routers converts `RequestValidationError` to `VALIDATION_FAILED` with `fieldErrors`, and a `V2Error` exception class (a subclass of `AppError`) has its own app-level handler that Starlette resolves before the legacy `AppError` handler (the most specific class wins). The legacy handlers and 422 behaviour for `dq` and `tr` are unchanged. A test asserts the legacy `/api/v1/dq/health` and a legacy 400 keep their exact bodies.
- **Snowflake identity (DEC-04, revised).** V2 opens connections with the existing `connect(settings)` helper and the existing `Settings` (the hard-coded ACCOUNTADMIN login on the temporary demo account). There is no pinned role, no `USE SECONDARY ROLES NONE` and no role self-check. V2 code never executes `USE ROLE`. Portfolio reads still touch only `V_APPLICATION_MONTH_STATUS`, `APPLICATION_COMPLIANCE` and the organisation view, through `repository.py`.
- **Month resolution (DEC-18).** `month.py` returns `scope.month` when supplied (`monthSource = selected`); otherwise the maximum `REPORTING_MONTHEND_DATE` of `V_APPLICATION_MONTH_STATUS` (`latest_available`), cached with the dataset probe. A grep gate (AG-13) forbids the literal `2026-10-31` in `backend/app` V2 packages and `frontend/src/v2` (fixtures and tests excepted).
- **Repository.** Functions are named by grain (`app_month_*`, `metric_row_*`, `metric_month_*`). Scope filters become bound parameters; `IN` lists get numbered placeholders; sort fields and dimensions come from enumerations. The three SQL shapes that need care: PD-02 (a per-metric aggregate over all rows), PD-14/PD-15 (self-join of a metric's rows on `EON_ID` between consecutive months) and `nonCompliantSince` (window functions, not a loop).
- **Definitions registry (DEC-17, OI-04, OI-09).** `definitions.py` is the single source: entries PD-01..PD-19 with id, name, definition, grain, scope, limitations, status, basis, `sinceVersion`, and `definitionsVersion = "pd-1"`. Services import ids from it; the `definitions` endpoint serialises it; the context builder renders its text for **both** agents; `render_agent_spec.py` renders the same text into agent specification v2 and into `20_agent_definitions_update.sql` (saving the previous specification text first, for rollback). A test checks that the rendered blocks and the registry agree.
- **Cache and fallback.** The TTL cache keys include `dataset.promotedAt`. A new `portfolio_gate` (same class as `Gate`, separate instance) controls fallback. The packaged JSON is a copy of the six export files placed in `app/fallback_assets/v2/` with a manifest; the mapper converts upper-case Snowflake names to contract names and sets `meta.source = "packaged"`. Endpoints without an extract return `503 FALLBACK_UNSUPPORTED` while Snowflake is down.
- **Handles and tokens.** `tokens.py` signs `conversationId` and `runId` as in contract 3.8. Verification is constant time. An invalid or edited value is `404 CONVERSATION_NOT_FOUND` or `RUN_NOT_FOUND`. Handles and tokens are never logged.
- **Thread I/O (`threads.py`).** One function, the call in contract 5.5.3. The first message omits `thread_id` and sets `"background": true` with the third argument `TRUE`. A follow-up sends `thread_id` and `parent_message_id` = `metadata.last_message_id`. Reads call `THREAD_MESSAGES(thread_id)` with no page cursor (A-13) and parse `message_payload`. A transient read error leaves the run `RUNNING` and is `503 THREAD_UNAVAILABLE` only on the conversation read. It does not import the legacy `agent_client`.
- **Run state (`runs.py`).** Pure function of (token, thread messages, clock). `RUNNING` until an assistant message has `parent_id` equal to the token's `userMessageId` (ids are not in time order). `COMPLETED` when that child exists; parse its payload. `FAILED / AGENT_EXECUTION_ERROR` when the thread is `IDLE` with no child or the payload records an error. `overdue` after 180 s. `FAILED / AGENT_TIMEOUT` after 600 s, and `COMPLETED` if the child appears later. Retry follows contract 5.5.3. No cancel. No in-process worker.
- **Context builder.** Stateless. Builds items by calling the Portfolio services (not SQL of its own), renders readable lines per item (12 lines, 400 characters), enforces the 12,000-character cap, computes the SHA-256 and the `MA2-REF` line, and rejects unknown item keys per surface. On `POST /agents/conversations` it rebuilds the context from the request and compares the hash (`409 CONTEXT_STALE`, `400 CONTEXT_INVALID`).
- **Parser.** Pure function, no I/O, tested against fixtures (contract 6.4) including `THREAD_MESSAGES` shapes captured in S0. It is the first agent component to build.
- **Precomputed investigations.** `precomputed.py` loads the manifest at start-up, verifies SHA-256 of each file on first read, and returns the content and stale flag for contract 4.20 and 4.21. A bad hash means that file is not served.
- **Observability.** Request id middleware scoped to V2 routes; one access-log line per request; run-state derivations logged with a hash prefix of the token; no message text, rows, rendered context or tokens in logs (a test asserts it with `caplog`).
- **Settings.** No new environment variable is required. Agent names, limits and the signing key derivation are code constants. `V2_SIGNING_KEY` is an optional override and is not part of the first release.

---

## D. One-shot execution order (REVISED)

The plan is one integrated delivery with stages that run in parallel where files do not overlap. It is adjusted to this repository in four ways: there is no component or E2E test tooling yet, so a tooling step precedes the page work; the legacy mount comes first because it touches the entry file every other frontend piece depends on; a baseline-preservation step (B0, A.5) precedes every change; The thread spike has already been run (contract 5.5.2) and is not repeated before coding. The only Snowflake changes left are applying agent specification v2 and generating the precomputed investigation files, both in step 10, both with the existing login.

### D.1 Stages

| Stage | Content | Exit criterion |
| --- | --- | --- |
| B0 Baseline | Preservation of untracked work and a new branch (A.5). | Archive and manifest exist; `BASELINE.txt` written |
| S0 Thread spike | Done on 2026-11-04. Both agents: SQL thread creation, background first message, background follow-up with `parent_message_id` = `metadata.last_message_id`, and Data-agent `system_execute_sql` results present in `message_payload`. Recorded in contract 5.5.2. Not a gate. | Passed. Do not run it again before building |
| S1 Platform (parallel lanes F, P, A0) | **F**: `resolveEntry`, `main.tsx`, `legacy-entry.tsx`, `App.tsx` basename, V2 shell and CSS port, `api/config|http|types`, hooks, test tooling (DEC-10). **P**: V2 error and envelope layer, definitions registry, month resolver, filters, cache, `/status`, `/filters`, `/definitions`. **A0**: parser for the `message_payload` shape in contract 6.4, `tokens.py`, run-state function, `limits.py`, `render_agent_spec.py` and the generated `20_agent_definitions_update.sql` (written, not executed). | CP1, CP2 |
| S2 Portfolio data and pages (parallel lanes P and U) | **P**: overview, trends, distributions, org, coverage, applications, then metrics list/preview/summary/trend/breakdowns/applications, then application detail/history and both investigation endpoints. **U**: Dashboard, Register and drawer, Metric Summary, both Investigations (without agent actions), Definitions, Architecture. Pages are built against fixtures first and switched to live endpoints at each checkpoint. | CP3, CP4 |
| S3 Agents (parallel lanes A and U2) | **A**: context builder, `threads.py`, `runs.py`, `conversations.py`, routers, export, `precomputed.py`. After approval: run `20_agent_definitions_update.sql`, then `generate_precomputed_investigations.py`, then review and accept files. **U2**: AgentHome, ContextReview, AgentPicker, ConversationPage, DatasetView, AnalysisView, `conversationStore.ts`, ChatWithAgentButton wired into Register, Summary, both Investigations and Dashboard. | CP5, CP6 |
| S4 Hardening | Reliability and security tests, E2E, accessibility pass, performance check on cold dashboard (nine parallel calls), restart-recovery drill, operations notes. | CP7 |
| S5 Release | Deployment (G), after the VM inspection gate (I). | Smoke tests pass |

### D.2 Ordered steps

0. B0: baseline preservation (A.5). Nothing else starts before it.
1. Record D.4 as closed for this demo (they are closed below). Generate `golden.json` and the contract fixtures. The thread spike is already done.
2. Add the frontend test tooling (DEC-10) so later steps can include component tests.
3. Legacy mount: `resolveEntry` with tests, `legacy-entry.tsx`, `main.tsx`, the basename edit. Verify with the existing six tests, `npm run build`, and the legacy route checks in F.2. **No V2 page work is merged before this passes.**
4. Backend envelope and errors, definitions registry, month resolver, filters and cache; unit tests.
5. V2 shell, styles, `api/*`, hooks; fixtures-based tests.
6. Parser, `tokens.py`, run-state function, `limits.py`, agent-spec renderer (pure, independent of everything else).
7. Dashboard endpoints and Dashboard page.
8. Metric endpoints, Register, drawer, Metric Summary.
9. Application endpoints, both Investigation pages (data side).
10. Context builder, `threads.py`, `runs.py`, `conversations.py`, routers, using the call in contract 5.5.3. Then run `20_agent_definitions_update.sql` with the existing login (save the previous specification text first) and generate, review and accept the precomputed investigation files.
11. Agent UI and the contextual entry points on every page.
12. Architecture and Definitions pages; Triage-removal and no-database grep gates; final integration, E2E, hardening.

### D.3 Integration checkpoints

| Id | Checkpoint | Who signs |
| --- | --- | --- |
| CP1 | Legacy mount verified on `npm run build` output served by `vite preview`: all legacy routes, refresh, query/hash, alias redirects. Existing tests green. | Frontend lead |
| CP2 | `types.ts` compiles against all fixtures; backend models serialise to the same fixtures (a shared JSON-schema or round-trip test). | Both leads |
| CP3 | Portfolio endpoints equal the golden values and reconcile with the snapshot and organisation extracts. | Backend lead |
| CP4 | Dashboard, Register, drawer, Summary and Investigations render live data with no hard-coded figures (grep gate). | Frontend lead |
| CP5 | Parser tests pass on fixtures shaped like contract 6.4 (tool use, tool result, `message_payload`). One live call per agent during this step confirms the same shape. Context test (A-3) and follow-up test (A-2) are part of this step, not a precondition for starting it. | Backend lead |
| CP6 | All twelve contract workflows pass in E2E against a running backend. | Both |
| CP7 | Release candidate: full test run, security checklist, deployment dry run. | Release owner |

### D.4 Decisions (closed for this demo)

| Id | Decision | Recommendation |
| --- | --- | --- |
| DEC-01 | Namespaces `/api/v1/portfolio` and `/api/v1/agents` under the existing `VITE_API_BASE_URL`. | Approve (contract 1.2). |
| DEC-02 | Polling for agent runs, not streaming. | Approve (contract 5.5). |
| DEC-03 | (REVISED) Conversation source of truth: Snowflake Cortex Agent threads read with `THREAD_MESSAGES`. No application database, no volume, no new service. Browser keeps list metadata in `localStorage` only. | Approve. Replaces the earlier volume-based store. |
| DEC-04 | (REVISED) Runtime identity: the backend's existing hard-coded ACCOUNTADMIN login (temporary demo account). No pinned role, no role self-check. OI-01 is an accepted demo risk. | Approve (owner instruction). |
| DEC-05 | Metric family is `null`; denominator scope is inferred (PD-02, PD-13). | Approve; supplying a real family list is a later data task. |
| DEC-06 | (REVISED) Context is built by the server from a small request (surface, scope, exclusions), shown for review, and rebuilt and hash-checked at conversation creation. The browser never sends context text. | Approve (contract 5.3). |
| DEC-07 | Legacy mounted by bootstrap plus router basename (A.4). | Approve. |
| DEC-08 | No SQL editing or user-supplied SQL in Data Explorer. | Approve. |
| DEC-09 | (REVISED) Conversation access by signed handle (no client key, no session). | Approve (contract 3.8). |
| DEC-10 | Add `@testing-library/react`, `@testing-library/user-event`, `jsdom` and `@playwright/test` as frontend dev dependencies. | Closed. Add them in step 2. |
| DEC-11 | Optional grants on the snapshot table and organisation view. | Not required; skip. |
| DEC-12 | Optional "Open the new app" link in the legacy shell. | Skip for now. |
| DEC-13 | No chart library; SVG components only (B.3). | Approve. |
| DEC-14 | Handles and run tokens are HMAC-signed and stateless; the key derives from the existing Snowflake credential; `V2_SIGNING_KEY` is an optional override. | Approve. |
| DEC-15 | Execution is the verified SQL call: `DATA_AGENT_RUN(..., TRUE)` with `"background": true` for the first message and for follow-ups. State comes from `THREAD_MESSAGES`. No REST token and no in-process worker. | Closed. Verified 2026-11-04 (contract 5.5.2). |
| DEC-16 | This demo does not add end-user authentication. Access is the signed handle, as with the legacy API. `get_principal` stays a one-function seam and is not built out. | Closed for the demo. Not a security redesign. |
| DEC-17 | The application is usable before specification v2, because the first message carries the month and the definitions. Step 10 still applies v2 in the same implementation, with the existing login. | Closed. Apply v2 in step 10. |
| DEC-18 | Reporting month: an explicit `scope.month` wins; otherwise the backend resolves the latest month; no literal month in V2 code. | Approve. |
| DEC-19 | Business-defined metric grouping is not invented; PD-19 groups by denominator treatment only. | Owner supplies a grouping later. |
| DEC-20 | Precomputed investigations cover all 24 metrics and the 50 non-compliant applications with the most open findings in the latest month. | Closed. |
| DEC-21 | No cancel in this release (SQL has no cancel call); "Stop waiting" is client-side. | Approve. |
| DEC-22 | No programmatic access token and no single-turn fallback. SQL created the threads and `THREAD_MESSAGES` kept the SQL tool results. | Closed. Verified 2026-11-04. |

---

## E. Parallelism and ownership

### E.1 Lanes

| Lane | Owner | Can start | Depends on |
| --- | --- | --- | --- |
| F platform | Frontend | S1 | contract |
| U pages | Frontend | S1 against fixtures | F shell, `api/*` |
| P portfolio backend | Backend | S1 | definitions registry, month resolver, errors (inside the lane) |
| A0/A agents backend | Backend 2 (or the same owner after P) | Parser, tokens, run-state function and spec renderer in S1; `threads.py` and the rest once `context/builder` can read Portfolio services (S2 CP3) | P services |
| U2 agent UI | Frontend | S3, against recorded agent fixtures | A models |
| Q quality and release | Either | S1 (test tooling), S4 | all |

The Portfolio endpoints are independent of one another once the shared layer exists, so S2 backend work splits cleanly into three streams: (1) Dashboard group, (2) metric group, (3) application group.

### E.2 Single-owner files (no concurrent edits)

| File | Owner |
| --- | --- |
| `API_CONTRACT.md` | Contract owner; changes require a version note |
| `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/legacy-entry.tsx` | Frontend lead (legacy mount) |
| `frontend/src/v2/routes.tsx`, `v2/api/types.ts`, `v2/styles/tokens.css` | Frontend lead |
| `frontend/package.json`, `package-lock.json` | Frontend lead |
| `backend/app/main.py` | Backend lead |
| `backend/app/portfolio/definitions.py`, `portfolio/repository.py`, `agents/registry.py`, `agents/parse.py` | Backend lead |

---

## F. Tests and acceptance

### F.1 Commands

VERIFIED existing:

| Purpose | Command (working directory) |
| --- | --- |
| Frontend unit tests | `npm test` (`frontend/`), runs `vitest run` |
| Frontend type-check and build | `npm run build` (`frontend/`), runs `tsc --noEmit && vite build` |
| Serve the production build locally | `npm run preview` (`frontend/`) |
| Backend tests | `pytest` (`backend/`) |
| Live Snowflake and Cortex tests | `RUN_LIVE_SNOWFLAKE_TESTS=1 pytest -m live` (`backend/`) |

PROPOSAL (need DEC-10): component tests in Vitest with `jsdom` and Testing Library (`vitest` environment set per test file with a docblock, so the six existing node-environment tests are unaffected); E2E with Playwright, `npm run build && npm run preview` plus a stubbed API for UI flows, and a second run against a real backend for the contract workflows. The exact script names (`test:e2e`) are added in S1.

API integration tests need no new dependency: FastAPI `TestClient` with the repository layer replaced by a fixture-backed implementation (offline) and a `live` variant that runs against Snowflake with the existing login.

### F.2 Acceptance matrix

**Legacy preservation (L)**

| Id | Check | Method |
| --- | --- | --- |
| L-1 | All six existing Vitest files pass unmodified. | `npm test` |
| L-2 | `npm run build` passes; `dist/index.html` contains no stylesheet link; every `href`/`src` begins with `/`; no `<base>`. | build plus script check |
| L-3 | `/legacy`, `/legacy/dashboard`, `/legacy/overview`, `/legacy/metrics`, `/legacy/metrics/DQ-001`, `/legacy/metrics/M001`, `/legacy/investigations/DQ-001`, `/legacy/architecture`, `/legacy/glossary` load by direct navigation and by refresh, with `?` query and `#` hash preserved where they existed. | E2E on `vite preview` |
| L-4 | In legacy, every internal link stays under `/legacy`; back links restore previous pages; filters in the URL survive refresh. | E2E |
| L-5 | Legacy investigations still run: start, poll, completed, failed, busy (429), using a stubbed API. | E2E, plus existing backend tests |
| L-6 | Legacy root aliases (`/dashboard`, `/metrics/DQ-001?x=1#a`, `/glossary`) redirect to `/legacy/...` keeping query and hash. | `resolveEntry` unit tests, E2E |
| L-7 | `/api/v1/dq/*` and `/api/v1/tr/*` responses and status codes are unchanged, including the 400 and 404 bodies. | existing backend tests plus a snapshot test of three legacy errors |
| L-8 | Legacy CSS is not loaded on V2 pages and V2 CSS is not loaded on `/legacy/*`. | marker-class check on loaded stylesheets in E2E |
| L-9 | V2 storage keys all start `ma2:`; legacy keys untouched. | unit test on the key helper, grep |

**New navigation (N)**

| Id | Check |
| --- | --- |
| N-1 | `/` is the Dashboard; nav shows Dashboard, Metric register, Agent, Architecture, Definitions & conventions. |
| N-2 | No "Triage" text, route, nav item, breadcrumb or link exists in `frontend/src/v2/` (grep gate); no `/overview` route in V2. |
| N-3 | Every V2 route supports direct load and refresh; unknown paths show the V2 NotFound. |
| N-4 | Architecture works in V2 with its walkthrough, and `/legacy/architecture` still works. |

**Metric workflows (M)**

| Id | Check |
| --- | --- |
| M-1 | Dashboard cards load independently; one failed endpoint shows a per-card error with Retry. |
| M-2 | Register search, sort, filter and paging persist in the URL and reproduce on refresh. |
| M-3 | The drawer opens from `?preview=`, shows every field in contract 4.13 from the API, with Provisional / Assumption / Not available chips. |
| M-4 | Drawer actions: Open Summary goes to `/register/:metricId`; Open Investigation goes to `/investigate/metrics/:metricId` (and to the application route when an `EON_ID` is chosen); Chat with Agent opens context review first. |
| M-5 | Summary shows definition and calculation steps, history, compliance and test distributions, coverage, organisation and legal-entity breakdowns, contributors, provisional list. |
| M-6 | Both Investigation pages show source data, history, derived values with definition ids, and an agent panel that is "not run" until a real run exists; no static explanation text anywhere. |
| M-7 | Unobserved months render as "Not observed" (hatched), never zero or compliant. |
| M-8 | Dashboard, Register and Summary contain no hard-coded numbers (grep for digit literals outside tests and fixtures). |

**Agent workflows (G)**

| Id | Check |
| --- | --- |
| AG-1 | Agent picker shows exactly the two names and descriptions from contract 5.2; nothing is preselected. |
| AG-2 | Context review shows chips, readable item blocks, removable optional items, required items locked, the exact text in a collapsed block, and no JSON viewer. |
| AG-3 | Conversations are bound to the chosen agent; the agent cannot change; a follow-up goes to the same agent; contextual conversations keep their chips. |
| AG-4 | Data Explorer shows SQL panel, results table, row count, truncation notice, Copy SQL, Export CSV, multiple queries, no-query state; no SQL editing. |
| AG-5 | The parser keeps `json.sql`, columns and types, `result_set.data`, `numRows`, `query_id`; correlates by `tool_use_id`; handles several blocks and several queries; never builds a dataset from prose (fixture tests, including the real A2_COUNT, A2_ROW, A2_READONLY shapes). |
| AG-6 | Lifecycle: `RUNNING`, `COMPLETED`, `FAILED` (`AGENT_ERROR`, `AGENT_TIMEOUT`), `overdue` at 180 s, late completion after `AGENT_TIMEOUT`, retry, busy 429, refresh recovery, restart recovery (state recomputed from run token plus thread), "Stop waiting" is client-only, and no cancel control or endpoint exists. |
| AG-7 | The browser sends no agent name, SQL, thread id or rendered context text: only a `ContextRequest` (surface, scope, exclusions), the reviewed `contextHash`, the message, `clientRequestId` and opaque handles (assert on recorded requests; backend request models use `extra = "forbid"`). |
| AG-8 | Live regression, not a spike: one call per agent returns evidence; a context call preserves `eon_id`, `metric_id` and month (A-3); a follow-up on the same thread keeps the same agent (A-2). The 2026-11-04 probe already passed the thread, background and tool-result checks. |
| AG-9 | Month precedence: an explicit `scope.month` is used in the context, the first message and the agent call even when a later month exists. |
| AG-10 | Latest-month resolution: with no `scope.month` the backend uses the maximum reporting month, reports `monthSource = latest_available`, and the first message shows that month. |
| AG-11 | Live, after agent specification v2: a PD-01 rate question to **both** agents returns the provisional rate with numerator and denominator and the provisional label. Before v2 this is a recorded known limitation (DEC-17). |
| AG-12 | Both agents receive the same `definitionsVersion` and the same definitions block; the rendered agent specification equals the registry (checksum test). |
| AG-13 | Grep gate: no literal `2026-10-31` in V2 backend or frontend code (fixtures and tests excepted). |
| AG-14 | Context stability: the first thread message contains the `MA2-REF` line with surface, month, `monthSource`, metric, application and hash; a follow-up uses the original context, not a rebuilt one. |
| AG-15 | Precomputed fallback: a run still `RUNNING` at 45 s with a file present returns `FALLBACK_STATIC` with the label "Pre-analysed ... Not a live run.", the file's date and the stale flag when the dataset or definitions version changed. |
| AG-16 | When the live run completes after a fallback was shown, the next poll returns `COMPLETED` and the page replaces the static content. |
| AG-17 | Chat never falls back: a slow or failed chat run stays running or failed; `fallback=precomputed` is rejected outside the two Investigation endpoints. |
| AG-18 | Precomputed assets: every file hash equals the manifest; a mismatching or missing file is not served; a target without a file has no fallback and shows the live state. |
| AG-19 | Thread continuation: a follow-up uses the thread in the handle and the last message id as parent; the agent key cannot be changed; a conversation reopened from `localStorage` after an API restart continues on the same thread. |
| AG-20 | Conversation metadata: `ma2:conversations` stores only the `SavedConversation` fields (no message text, SQL or rows), holds at most 50 entries, and a `404` marks the entry unavailable. |
| AG-21 | Duplicate protection: the same `clientRequestId` returns the original response with `Idempotent-Replay: true`; a different body with the same key returns `IDEMPOTENCY_KEY_REUSED`; a second submit while the thread has an unanswered message returns `RUN_IN_PROGRESS`. |

**Data correctness (D)**

| Id | Check |
| --- | --- |
| D-1 | Every Portfolio endpoint equals the golden values (F.3). |
| D-2 | Application counts use distinct applications; `TOTAL_RFB` is never summed across metric rows (a test with a two-row application, EON611195, expects open findings 3). |
| D-3 | BUSINESS_ORG and BU results are separate and match `org_contribution.json` in the fallback tests and the Oct values in the contract. |
| D-4 | Rates equal `SUM(IS_NUMERATOR)/SUM(IS_DENOMINATOR)` and are `null` when the denominator is 0; deltas use PD-16. |
| D-5 | First-month movement is `null`; unobserved months are explicit. |
| D-6 | Reconciliation: snapshot extract and application-month aggregates agree for all 12 months (live test). |
| D-7 | PD-02 classification: 6 metrics `INCLUDES_PENDING`, 18 `EXCLUDES_PENDING`. |

**Reliability and security (R)**

| Id | Check |
| --- | --- |
| R-1 | V2 opens Snowflake connections only through the existing `connect(settings)` helper and contains no `USE ROLE`, no role literal and no credential literal (grep gate). |
| R-2 | Hostile filter, sort and id values return 400 or 404, never reach SQL as text (tests with SQL metacharacters). |
| R-3 | Owner names absent by default and in agent context unless switched on. |
| R-4 | Logs contain no message text, context text, rows, handles or tokens (`caplog` assertion). |
| R-5 | CORS is unchanged: preflight allows only `Content-Type`; methods remain `GET`, `POST`; V2 requests carry no custom header (recorded-request assertion). |
| R-6 | Handle integrity: an edited thread id, agent key or signature, or a bare integer thread id, returns `404 CONVERSATION_NOT_FOUND` (`RUN_NOT_FOUND` for tokens); a handle never reveals the agent object name. |
| R-7 | Snowflake outage: packaged fallback serves the six Dashboard endpoints with `source: packaged` and a visible notice; other endpoints return `FALLBACK_UNSUPPORTED`; agents fail honestly and never produce static answers outside contract 6.7. |
| R-8 | Capacity: the fifth concurrent in-flight run returns `AGENT_BUSY`; legacy investigations still start. |
| R-9 | Restart recovery: with the thread reader stubbed, clearing every in-memory structure leaves the same run token reading the same state and a finished answer still readable. |
| R-10 | Context integrity: a changed dataset promotion, definitions version or request returns `409 CONTEXT_STALE`; a tampered hash returns `400 CONTEXT_INVALID`; nothing is sent to the agent in either case. |
| R-11 | No database: grep gate over `backend/` (code, `requirements.txt`, `Dockerfile`, `docker-compose.yml`) and `frontend/` for `sqlite`, `/data` mounts and volume declarations finds nothing new (the gate searches for the string that must not appear); V2 start-up and all V2 tests pass with file writes blocked. |
| R-12 | Thread failures: a transient `THREAD_MESSAGES` error leaves a run `RUNNING` and returns `THREAD_UNAVAILABLE` only for the conversation read; the run turns `FAILED / AGENT_TIMEOUT` at 600 s and `COMPLETED` if the answer arrives later. |
| R-13 | No in-process agent worker exists. A run submitted on one Snowflake connection is still readable, with the same `userMessageId` child, from a second connection. |

### F.3 Golden values (REAL, from the contract examples)

Put in `golden.json` and used by D-1: Oct 2026 overview (923, 300, 293, 247, 1,870, 1,096; movement 132/117/131/111/432); September reporting 937 and non-compliant 278; 12-month reporting and non-compliant series; risk `P1 99/35`, `P2 358/111`, `P3 357/114`, `P4 109/40`; business-organisation level-1 counts (eight groups) and BU level-1 counts (six groups); Oct compliance rows (463, 324, 183, 126); Oct test status rows (736, 168, 109, 83) and results (459, 273, 4); data coverage (1,500; 923; 577; 375; 139; 24; 11,399; 9,784); `M325402` (Oct 34/62, Sep 33/56, trend of 12 rates, composition 71/18/7, `Super_Division_04` 21 applications 5 non-compliant 10/15); the four largest metrics' Oct rates; `EON611195` (two October rows, open findings 3, observed in 7 months); PD-02 classification; agent fixtures from the real runs.

### F.4 Definition of done per feature

A feature is done when: its endpoint or page matches the contract; fixture and unit tests pass; the relevant acceptance rows pass; no new TypeScript error; `npm run build` and `pytest` are green; and, for agent features, the live checks have been run once and recorded.

### F.5 Traceability: workflow to rendered UI (NEW)

Each row names the chain that must exist and be tested. "Test" refers to F.2 ids; every chain also has a fixture-based frontend test and a backend contract test.

| Workflow (contract) | Frontend | Endpoint(s) | Backend path | Response to rendered UI | Test |
| --- | --- | --- | --- | --- | --- |
| Dashboard load (8.1) | `DashboardPage`, cards, `api/portfolio.ts`, `useApiQuery` | `filters`, `overview`, `trends`, `distributions/*`, `org/contribution`, `data-coverage`, `applications` | router, services, `repository.py`, cache, `month.py` | each card renders its own response; per-card error with Retry | M-1, M-7, M-8, D-1 to D-5 |
| Register (8.2) | `RegisterPage`, `MetricTable`, `useUrlState` | `filters`, `metrics` | services, repository | rows, sparkline, pager; URL reproduces state | M-2 |
| Metric preview and context (8.3) | `PreviewDrawer`, `ChatWithAgentButton`, `ContextReviewDialog`, `contextClient.ts` | `metrics/{id}/preview`, `agents/context/preview` | preview service, `context/builder.py`, `definitions.py` | chips, items, exact text, hash | M-3, M-4, AG-2, AG-14 |
| Metric Summary (8.4) | `MetricSummaryPage` sections | `metrics/{id}`, `/trend`, `/breakdowns`, `/applications` | services, repository | definition and calculation, history, distributions, contributors, provisional chips | M-5, D-2 to D-4 |
| Metric Investigation (8.5) | `MetricInvestigationPage`, `AgentAnalysisPanel` | `investigations/metrics/{id}?runId=` | investigation service, `runs.py`, `precomputed.py` | observations and derived values; agent panel `NOT_RUN` / `RUNNING` / `COMPLETED` / `FALLBACK_STATIC` / `FAILED` | M-6, AG-15, AG-16, AG-18 |
| Application Investigation (8.6) | `ApplicationInvestigationPage`, `StatusStrip` | `investigations/applications/{eonId}?runId=` | application service, `runs.py`, `precomputed.py` | history with hatched unobserved months; agent panel as above | M-6, M-7, D-2, D-5 |
| General Analysis chat (8.7) | `NewConversationPage`, `Composer`, `AgentPicker` | `agents`, `agents/context/preview`, `POST agents/conversations` | `context/builder.py`, `tokens.py`, `threads.py` | explicit agent choice, handle saved in `ma2:conversations`, run starts | AG-1, AG-3, AG-7, AG-19, R-10 |
| Contextual Analysis chat (8.8) | `ChatWithAgentButton` then `ConversationPage`, `GroundingRail` | `POST agents/conversations`, `GET .../context`, `POST .../messages` | `conversations.py`, `threads.py` | grounding chips, follow-ups on the same thread | AG-3, AG-14, AG-19 |
| General Data Explorer (8.9) | `ConversationPage`, `DatasetView` | as 8.7 | `parse.py`, `threads.py`, `export.py` | SQL, columns, rows, row count, truncation, CSV export | AG-4, AG-5 |
| Contextual Data Explorer (8.10) | as 8.8 with `DatasetView` | as 8.8 | as 8.9 | real SQL and rows from the thread (A-9) | AG-4, AG-5, AG-8 |
| Running execution (8.11) | `useAgentRun`, `RunStatus` | `GET agents/runs/{runId}`, `GET agents/conversations/{handle}` | `runs.py`, `limits.py` (coalescing) | events, elapsed, overdue notice, Stop waiting, resume after refresh or restart | AG-6, R-9, R-12 |
| Agent or tool failure (8.12) | `RunStatus`, `agent/errors.ts` | same | `runs.py`, parser errors | failed state with code, Retry, honest messages | AG-6, AG-21 |
| Slow investigation fallback (8.13) | `AgentAnalysisPanel` | investigation endpoints with `runId` and `fallback=precomputed` | `precomputed.py` | labelled static analysis, stale flag, live swap-in | AG-15 to AG-18 |
| Legacy and routing | `resolveEntry`, `legacy-entry.tsx` | none | none | `/legacy/*` unchanged; aliases redirect | L-1 to L-9 |

---

## G. Deployment (REVISED)

No new environment variable, volume, Dockerfile, compose, `requirements.txt` or CORS change is needed. The Snowflake actions are the ones in A.2, performed once after approval. Nothing in this section has been run, and the VM was not inspected (gate V-1 to V-5, section I).

### G.1 Frontend (Cloudflare Pages)

- Settings are unchanged (root `frontend`, build `npm run build`, output `dist`, `VITE_API_BASE_URL` as documented in the README).
- The entry bootstrap and chunks are produced by the same build. Pages serves nested paths with `index.html` when there is no top-level `404.html` (A-6, documented behaviour); verify on a preview deployment before production. If the check fails, add `frontend/public/_redirects` with `/* /index.html 200`, then redeploy.
- Preview deployments call the API from a different origin: the API's `CORS_ORIGINS` (existing variable) must list the preview origin while it is being tested; remove it afterwards. This is an operations step, not a code change.

### G.2 Backend (Oracle VM, Docker, Nginx)

1. Build and start with the existing flow (`docker compose up --build` from the compose project). The image is built where the compose file lives; it is not pushed from this repository. The compose file is not edited.
2. V2 stores nothing locally: no volume is mounted and no path must be writable. A restart loses only in-memory helpers (poll coalescing, duplicate cache, rate counters, bounded caches); conversations and runs are recovered from the Snowflake threads and the browser's handles.
3. Nginx: no change expected (A-7). Verify (V-3) that `/api/v1/portfolio/...` and `/api/v1/agents/...` pass through, `OPTIONS` preflights are answered by the backend, and the read timeout is at least 30 s. V2 requests are short (agent calls do not hold HTTP connections open).
4. No new dependency: HMAC and hashing use the Python standard library; the Snowflake connector is already installed.
5. Existing health check stays: `/api/v1/dq/health/ready`. V2 readiness is `/api/v1/portfolio/status`.
6. Snowflake actions in step 10, with the existing login, each recorded: run `20_agent_definitions_update.sql` (the previous specification text is saved first) and generate, review and accept the precomputed investigation files, then include them as `fallback_assets`. The thread probe is already done.

### G.3 Order, smoke tests, rollback

Order: (1) backend, additive, legacy unaffected; (2) smoke the backend; (3) Pages production deployment; (4) smoke the site.

Backend smoke (public host `https://metrics-analyzer-backend.sdeashirvad.com`):

- `GET /api/v1/dq/health` and `/api/v1/dq/health/ready` still return OK.
- `GET /api/v1/portfolio/status` shows the dataset, `definitionsVersion`, and both agents `available`.
- `GET /api/v1/portfolio/overview` returns the golden Oct values.
- One `POST /api/v1/agents/context/preview`, one conversation per agent, one follow-up on the same thread. Restart the container during a run: the same run token still resolves (R-9).
- An OPTIONS preflight from the Pages origin still allows only `Content-Type` (R-5).

Site smoke (`https://metrics-analyzer-poc.pages.dev`):

- `/` Dashboard, `/register`, `/register/M325402`, `/investigate/applications/EON611195`, `/agent`, `/architecture`, `/definitions`.
- `/legacy/dashboard`, `/legacy/metrics/DQ-001`, `/legacy/investigations/DQ-001` by direct load and refresh; `/dashboard` redirects to `/legacy/dashboard`.

Rollback: the backend change is additive. Redeploy the previous commit (`docker compose up --build`); there is no volume or migration. For the site, use the Pages rollback to the previous production deployment, which also restores the old root behaviour. For agents, re-apply the saved previous specification text. Threads created by tests stay in Snowflake and are harmless. Legacy keeps working throughout.

---

## H. Completion checklist (REVISED)

- [ ] B0 baseline preserved: archive, manifest and branch exist; manifest re-verified at the end (A.5).
- [ ] D.4 is the demo decision set. Do not reopen DEC-15, DEC-16 or DEC-22.
- [ ] Fixtures and `golden.json` committed.
- [ ] Do not repeat the 2026-11-04 thread probe before coding. Parser fixtures follow contract 6.4.
- [ ] Legacy mount merged and CP1 passed before any V2 page merge.
- [ ] Existing six frontend tests and all backend tests pass unchanged.
- [ ] Every contract endpoint implemented, with tests and golden checks; none returns a hard-coded figure or month.
- [ ] Definitions registry published; every non-source field shows a Provisional, Assumption or Not available chip; both agents use the same `definitionsVersion`.
- [ ] Triage absent from V2 (grep gate), content folded into Dashboard and Register filters.
- [ ] Architecture works in V2 and in legacy.
- [ ] Both agents work: context review, explicit agent choice, thread-based conversations, follow-ups, run lifecycle, restart recovery, retry. No cancel.
- [ ] Parser fixes the dropped-tool-result defect (SQL, columns, rows, row count, query id, truncation, errors, warnings).
- [ ] Browser never sends an agent name, SQL, thread id or rendered context text.
- [ ] No application database, volume or new service anywhere in the repository (R-11).
- [ ] Precomputed investigation files generated, reviewed, hashed; fallback tests pass; chat never falls back.
- [ ] A-1 to A-14 each confirmed or recorded as accepted risk.
- [ ] Security and reliability rows R-1 to R-13 pass.
- [ ] VM inspection gate done; deployment dry run, smoke tests and rollback rehearsed.
- [ ] Open items OI-01 to OI-15 reviewed with the owner; none silently dropped.

---

## I. Implementation Readiness and External Dependencies (NEW)

### I.1 Implementable now (no external action)

- B0 baseline preservation, branch, legacy mount and its tests, and the frontend test tooling from DEC-10.
- The V2 shell, styles, `api/*`, hooks, components, and every page built against fixtures.
- The whole Portfolio backend: envelope and errors, definitions registry, month resolver, filters, repository, services, cache, packaged fallback, `/status`, `/definitions`. Live checks use the backend's existing login.
- Pure agent pieces: parser (with fixtures from the repository's stored runs), `tokens.py`, run-state function, `limits.py`, context builder and hash, export, `precomputed.py` loader.
- Writing (not executing) `render_agent_spec.py`, `20_agent_definitions_update.sql` and `generate_precomputed_investigations.py`.
- Fixtures, `golden.json`, grep gates, and the traceability tests of F.5.

### I.2 Needs an administrator or the owner (approval or an action outside the code)

- Step 10 runs `20_agent_definitions_update.sql` with the existing login (it alters both agent specifications; the previous text is saved first). This is part of the implementation, not a later phase.
- Approval and credit use for about 74 agent calls to generate the precomputed investigations, and a human review of each file.
- Adding the Pages preview origin to the existing `CORS_ORIGINS` during preview testing.
- Whoever has VM access rebuilds and restarts the backend container.

### I.3 Needs VM inspection (not performed; nothing here is claimed as verified)

| Gate | Check | Why it matters |
| --- | --- | --- |
| V-1 | The compose file actually used on the VM: image build context, restart policy, memory limit, user, any volume | The repository's compose has no restart policy; a crash may not recover on its own |
| V-2 | Whether the VM serves any of the frontend or only the API | The brief says Pages serves the frontend; confirm |
| V-3 | Nginx: `/api/` forwarding for the two new namespaces, `OPTIONS` handling, read timeout of at least 30 s, no response-size cap below 5 MB | New endpoints must pass through unchanged |
| V-4 | Whether the client address is forwarded (for example `X-Forwarded-For`) | Only needed for an optional per-IP limit |
| V-5 | Free memory against the 512 MB container limit, uvicorn worker count (1), log rotation | Agent parsing buffers up to 5 MB per message |

### I.4 Decisions closed for this demo

These are decided. Implementation does not wait on them and does not invent a different answer.

- DEC-15 and DEC-22: the verified SQL thread call. No token, no extra worker, no single-turn mode.
- DEC-16: no end-user login in this demo. Handles only.
- DEC-04: the existing ACCOUNTADMIN connection. No new user and no new role.
- DEC-05 and DEC-19: family stays "not available"; PD-19 groups by denominator treatment. A real family list is data the owner may supply later. It is not required to build or to ship.
- DEC-17: ship the context-carried definitions immediately, and apply specification v2 in step 10 of the same build.
- DEC-10: add the test dev dependencies in step 2.
- DEC-20: 24 metrics and 50 applications, as written.
- DEC-21, OI-13, OI-14, OI-15: no cancel, browser-local conversation lists, in-memory counters. Accepted.
- `METRICSanalyzer1@` stays where it is. Removing it is not required to start. Do not read it, commit it or delete it. `frontend/.env.production` stays. Confirm it holds only the public API base URL before any commit.

Provisional definition labels stay until the owner confirms each PD item. That confirmation removes a label. It does not block the build.

### I.5 Readiness verdict

The one-shot implementation is ready to start at B0.

The thread behaviour the agent code depends on was run against both agents on 2026-11-04 and is specified in contract 5.5.3. Portfolio, frontend, agent gateway, parser and precomputed-file loader can be built from these two documents. Step 10 applies the agent specification update and generates the precomputed files with the existing login. Deployment still needs the VM inspection in I.3; that inspection does not block writing the code. No application database is part of the build.

