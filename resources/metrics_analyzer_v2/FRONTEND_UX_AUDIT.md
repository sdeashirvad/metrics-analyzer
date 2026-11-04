# Metrics Analyzer V2: Frontend UX Audit

Audit date: 2026-11-04. Application under test: Vite dev server `http://127.0.0.1:5173/`, API `http://127.0.0.1:8080/api/v1`, live Snowflake (up during the audit).

This is an evidence-based audit of the running application. It does not rely on earlier audit notes. Where something could not be verified, it is stated in section G.

## How the audit was done and its limits

- Every route in `frontend/src/v2/routes.tsx` was opened in the Cursor embedded browser, data was allowed to settle, and the page was inspected through the DOM (headings, text, hrefs, geometry, accessibility names, font sizes, tap-target sizes).
- Live interactions were exercised: filters, drill-downs, preview, Escape, Agent selection, one live message to each Agent, reload recovery, Architecture Play/Pause.
- Responsive behaviour was measured by loading each route inside same-origin iframes at 1440, 1366, 1280, 1024, 768 and 390 px and reading geometry, overflow and layout state. These are real layout measurements, not estimates.
- Limit on screenshots: the embedded browser window is about 776 x 916 px. Emulated wide viewports produced tiled or stale frames, so pixel screenshots exist only at the real 776 px width. Wide-viewport findings (1280 to 1440) come from DOM geometry, not images. All screenshots are in `resources/metrics_analyzer_v2/ui_audit/frontend_ux/`.
- The read budget on Snowflake reads is 5 s. One cold first load of `/register` after idle failed with "This response has no packaged extract for the current request." (see O-01). Reloading worked. This is recorded as an offline-coverage finding, not a design defect.

## A. Executive assessment

| Dimension | Score (1-10) | Basis |
|---|---|---|
| Visual craftsmanship | 6 | Clean cards, calm palette, good Agent composer. Undermined by 9 distinct font sizes (10 to 15 px, tokens define only 12/13/14/16), a second private palette in `DashboardPage.css`, and raw identifiers shown as titles. |
| Information architecture | 5 | Summary, Investigation and Dashboard repeat the same counts and formula text. Investigation is dominated by a 6,015 px AI panel. Metrics have no human name, only `M340202`. |
| Interaction quality | 6 | All drill-downs, filters, preview open/Escape/focus-return, Agent send and reload recovery work. Weaknesses: misleading KPI destination, Preview chat dialog, listbox semantics. |
| Design consistency | 5 | Two token systems, three card radii, mixed button hierarchies (two filled primaries in Preview), Agent response renderers differ in duplication behaviour. |
| Responsive quality | 5 | No page-level horizontal overflow at any width. But the sidebar becomes a 157 to 252 px top bar at 768 px and below, Investigation tables clip at 1280 to 1440 px, and application tables clip at every width. |
| Enterprise readiness | 5 | Data is credible and consistent with the provisional rules, but a transient Snowflake slowness produces a hard error on Register, Summary, Investigation and several dashboard cards. |
| Agent experience | 7 | Two-agent choice, single-box composer, context rail, rich Analysis rendering (markdown, table, SQL, suggestions), fast completion (about 22 s and 20 s observed). Held back by route-variant inconsistency, duplicated Data Explorer text, truncated titles. |

Overall: a functional and honest analytical POC with a strong Agent core, but not yet premium. The main drags are an overloaded Investigation page, duplicated explanatory content, token fragmentation and missing offline coverage.

## B. Route-by-route audit

### B1. `/` Dashboard

- Data loaded: yes, all six cards (after Snowflake responded within budget). Packaged fallback exists only for overview, trends, testing, org, risk, applications, and only for the default scope and latest month.
- Interactions tested and working: KPI links (`/register`, `/register?hasNonCompliant=true`, `/?explore=attention&attention=noCompletedTest`), org bar to `?l1=`, legal bar to `?legalEntity=LE2048`, View all (org, legal, attention) to `?explore=`, trend point to `?month=2025-11-30`, attention tabs, attention rows to application investigation.
- Strengths: coherent two-column layout; equal-height cards; drill-down everywhere; month changes through the chart.
- Problems:
  - D-01 "Ask about this view" is not the standard label (`Ask Agent`).
  - D-02 "Open findings" KPI links to the same register filter as "Non-compliant" (`hasNonCompliant=true`). The destination does not show findings.
  - D-03 Legal entities show `Legal_Entity_07` but filter to `LE2048`; Investigation shows `LE4023`. Same entity, two identities.
  - D-04 Two different "non-compliant" numbers on one screen: 300 applications (KPI) and 324 metric rows (Compliance mix). Labelled, but easy to misread.
  - D-05 Fine print is heavy: Testing alone has five secondary lines, including "923 applications reporting" repeated and a coverage sentence.
  - D-06 The trend chart has unlabelled gridlines and three axis labels, with no values visible without hover.
  - D-07 Organisation and Legal entity lists are eight rows each plus View all. The brief says to avoid long legal-entity lists on the dashboard.
- Unnecessary: the "Application count, separate from the rows above" sentence, the coverage sentence, the repeated reporting count.
- Missing: a visible as-of / data-source note (the status bar says only "Demo dataset · Oct 2026").
- Layout defects found in this audit's earlier passes were fixed (column balance, org/legal pair, trend width). Remaining: Testing distribution stretches to match Movement and shows extra internal spacing.
- Evidence: `dashboard_776_top.png`; geometry at 1440: two columns, cards at x264 and x837.

### B2. `/register`

- Data loaded: yes (24 metrics, 24 rows on one page of 25). One cold first load failed once (O-01).
- Interactions tested: RAG multi-select (URL `?rag=red`, 10 red rows), sort control present, Preview open and Escape (focus returns to the Preview button), `?q=` and `?sort=` via URL.
- Strengths: URL-driven filters; clear RAG pills with provisional band note; sparklines.
- Problems:
  - R-01 The metric column is only an ID; no name or family (the API payload has `family: null` and no name, so this is a data limitation; the UI must not invent names).
  - R-02 Filter area is two stacked panels (scope bar plus six controls), about 290 px before the table at 776 px.
  - R-03 `.menu-pop` has `role="listbox"` but contains `label`/`checkbox` children, not `option`s.
  - R-04 Every row has a link named "Provisional definition PD-01"; 24 identical accessible names.
  - R-05 Preview shows two filled primary buttons ("Open Summary / Details" and "Chat with Agent") with equal weight; no metric name or definition line.
  - R-06 Preview "Chat with Agent" opens a `Dialog` containing `ContextComposer`. This contradicts the mandatory navigation contract (see section D of the execution plan). The only permitted contextual exception must navigate to `/agent`.
  - R-07 The info "i" icon wraps under the rate at narrow widths.
  - 28 controls are shorter than 32 px.
- Preview behaviour measured at 1440: drawer x579, width 500, y72, height 630, centred in the content area. At 776 px it becomes a bottom sheet (correct). Escape closes it and returns focus to the trigger.
- Evidence: `register_776_top.png`, `register_preview_776.png`.

### B3. `/register/:metricId` Metric Summary (checked M340202)

- Data loaded: yes.
- Strengths: clear calculation block, rate over time, status mix by month.
- Problems:
  - S-01 Page title is the ID only.
  - S-02 The Breakdown dimension tabs show raw API keys: `org`, `legalEntity`, `tier`, `risk`, `lifecycle`, `complianceReason`, `testStatus`.
  - S-03 The raw formula `SUM(IS_NUMERATOR) / SUM(IS_DENOMINATOR) over metric rows ...` is repeated here and on Definitions. The brief says definitions belong in one place.
  - S-04 "Chat with Agent" links to `/agent?focusMetric=M340202`. The contract says Summary opens `/agent` with general portfolio context.
  - S-05 Summary and Investigation both show Rate, Applications, tests and contributors; the two pages overlap.
- Evidence: DOM report (h2: Calculation, Status and testing, Rate over time, Breakdown).

### B4. `/investigate/metrics/:metricId` (checked M340202)

- Data loaded: yes, with a prepared bundle.
- Strengths: Path to Green wording is honest (proposals only, no owners, "Already inside the healthy band"); contributors and affected applications are useful.
- Problems:
  - I-01 (Critical against the new scope) An embedded `AgentAnalysisPanel` occupies a sticky 380 px column that is 6,015 px tall (x1013, y155) and includes its own follow-up composer. It squeezes the main column to 733 px. At 1440 and 1280, two of the three tables clip horizontally; at 390 px, three tables clip and 310 elements extend past the viewport.
  - I-02 The prepared narrative shows raw markdown headers (`## Why it needs attention (evidence)`) as literal text.
  - I-03 A raw parser warning, "More than one query was returned.", is shown as a callout.
  - I-04 Logical conflict: the metric is Healthy (44.5%, below 45%), Path to Green says "Already inside the healthy band", but the prepared analysis opens with "The data can't tell us what 'the provisional green band' is." The prepared bundles were chosen by non-compliant count, which picked a healthy metric.
  - I-05 The page is 6,226 px tall because Affected applications is a long table; there is no progressive disclosure.
  - "Tests" appears as a card of three sentences that repeats the "Tests" KPI.
- Evidence: `investigation_metric_776_top.png`; geometry `[stack 733 x 2396][analysis-panel 380 x 6015]`.

### B5. `/investigate/applications/:eonId` (checked EON845019)

- Data loaded: yes.
- Problems:
  - I-06 "Explain with AI" links to `/agent?eonId=EON845019`, which seeds an application. The contract allows only the Register Preview to seed context.
  - I-07 History is shown twice: a 12-cell strip and a 12-row list of "Not observed".
  - I-08 The "Metrics this month" and "Metric months" tables clip horizontally at every width tested (390 to 1440).
  - I-09 Identity chips (Non-compliant, Failed test, No prior month) are good; "Owners / Show owner names" is a collapsed control with no explanation of why it is hidden.
- Evidence: `investigation_application_776_top.png`.

### B6. `/agent`, `/agent/:agentKey`, `/agent/:agentKey/:conversationId`

- Data loaded: yes. Agent list and context preview load.
- Live tests (one message each, as approved):
  - Analysis & Investigation: question about the organisation with the most non-compliant applications; completed in about 22 s; rendered markdown, bold, lists, a table, a SQL block, a "Copy SQL" button and three follow-up suggestions.
  - Data Explorer: counts by super division; completed in about 20 s; rendered interpreted intent, SQL, an 8-row result table (9x3 including header) and an Export action.
- Reload recovery: verified. Reloading `/agent/data/<id>` restored both messages.
- Follow-up send: not tested (no additional live messages allowed). The follow-up composer ("Ask a follow-up") is present.
- Strengths: single-box composer, clear two-card choice, context rail with scope, reporting period, selected entity, filters, definitions; `?focusMetric=M340202` populated the rail with "Metric M340202".
- Problems:
  - A-01 Route variants are not one workspace: `AgentHome` and `NewConversationPage` render `AgentWorkspace` (with context rail and agent switch), but `ConversationPage` is a different layout with only a collapsed "View context" and no rail.
  - A-02 Data Explorer repeats the interpreted-intent text (once as a lead paragraph, again as "Interpreted intent") and the DOM contains two identical SQL `pre` blocks.
  - A-03 The conversation H1 is truncated at 60 characters with no ellipsis ("...applications i").
  - A-04 At 768 px and below the left "Recent" list is placed inside the top bar, making it 237 to 252 px tall.
  - A-05 At tablet width the context rail is behind a "Context" toggle; the helper "Choose an Agent above to enable sending." sits inside the composer.
  - A-06 Wide Analysis tables or SQL inside bubbles: no horizontal overflow was found (`tableOverflow: false`).
  - A-07 Live-chat-unavailable state was not exercised (Snowflake was up).
- Evidence: `agent_landing_776.png`, `agent_analysis_response_776.png`, `agent_data_explorer_response_776.png`.

### B7. `/architecture`

- Data loaded: static page, loads instantly.
- Interactions tested: Play advanced to "Step 2 of 9: Call the API over HTTPS", Pause toggled, 26 interactive nodes.
- Strengths: the walkthrough works and node states are legible.
- Problems:
  - AR-01 The walkthrough title says "Trace a Data Quality investigation", which is the earlier release's wording.
  - AR-02 At narrow widths nodes occupy about 470 of 700 px and the detail panel stacks below.
- Preserve: yes (the brief requires it).
- Evidence: `architecture_776.png`.

### B8. `/definitions`

- Data loaded: yes (21 cards, 5,799 px).
- Strengths: labels (Provisional, Assumption, Documented rule), consistent card structure, correct RAG and green rules.
- Problems:
  - DF-01 No in-page navigation, grouping, or search over a 5,800 px page.
  - DF-02 Formula text uses raw field names (`IS_NUMERATOR`).
- Evidence: `definitions_776.png`.

### B9. `*` Not found

- Renders; the top bar is 448 px tall at 390 px.

## C. Issue register

| ID | Route | Component | Category | Severity | Observation | Evidence | User impact | Recommendation | Scope |
|---|---|---|---|---|---|---|---|---|---|
| I-01 | Investigation (metric, app) | `AgentAnalysisPanel` | Information architecture | Critical | Embedded 380 px sticky Agent column, 6,015 px tall, with own composer; main column shrinks to 733 px; tables clip | Geometry: stack 733 px, panel 380 x 6015; `tbl[false,true,true]` at 1440 | Violates the single-Agent-workspace rule; harms diagnosis | Remove the interactive panel; replace with a read-only Prepared Analysis section and a heading-level Ask Agent link | `features/investigation/AgentAnalysisPanel.tsx`, `MetricInvestigationPage.tsx`, `ApplicationInvestigationPage.tsx`, `styles/pages.css` |
| R-06 | Register | `ChatWithAgentButton` (contextual) in Preview | Interaction | High | Preview "Chat with Agent" opens a Dialog | Source `ChatWithAgent.tsx` lines 280-310; observed second dialog in prior pass | Contradicts contract (must navigate to `/agent`) | Navigate to `/agent` with bounded ids; rail shows context; user selects Agent | `ChatWithAgent.tsx`, `RegisterPage.tsx`, `AgentPages.tsx` |
| S-04, I-06 | Summary, App Investigation | `ChatWithAgentButton`, `Explain with AI` | Interaction | High | Links seed `focusMetric` / `eonId` | hrefs `/agent?focusMetric=M340202`, `/agent?eonId=EON845019` | Silent contextual seeding outside the allowed exception | Plain `/agent` (portfolio context) | `MetricSummaryPage.tsx`, `ApplicationInvestigationPage.tsx`, `ChatWithAgent.tsx` |
| A-01 | Agent routes | `AgentWorkspace` vs `ConversationPage` | UX / consistency | High | Conversation route has a different layout, no context rail or agent switch | Source `AgentPages.tsx`; DOM | Agent feels like two products | One workspace shell with conversation state | `AgentPages.tsx`, `styles/pages.css` |
| O-01 | Register, Summary, Investigation, Compliance mix, Legal, Coverage | `portfolio/services/*` fallback | Resilience | High | One cold load returned "This response has no packaged extract for the current request." | Observed on `/register`; source `runtime.py` / `metrics.py` `_no_fallback` | A slow Snowflake read produces a hard error | See execution plan section 7 (offline-first) | `backend/app/portfolio/*`, `fallback_assets/v2/*` |
| I-02 | Investigation | Prepared analysis markdown | Visual | High | Literal `##` headings in prepared text | Panel text: "## Why it needs attention (evidence)" | Looks unfinished | Render with the existing markdown component | `components/markdown`, `AgentAnalysisPanel.tsx` |
| I-04 | Investigation | Prepared bundle selection and Path to Green | IA | Medium | Healthy metric (44.5%) is the top "prepared" one; analysis says it cannot define green while Path to Green says already healthy | Page text | Contradictory message | Prefer metrics outside the green band; align narrative to the central threshold | `backend/app/portfolio/prepared.py`, `investigations.py` |
| I-03 | Investigation | Parse warnings | Visual | Medium | Callout "More than one query was returned." | DOM `.callout` | Internal parser leak | Hide parser warnings from users | `MessageViews.tsx`, `AgentAnalysisPanel.tsx` |
| A-02 | Agent | `MessageViews.tsx` | Visual | Medium | Intent text and SQL duplicated in Data Explorer | Two identical `pre` blocks; "Interpreted intent" repeats lead | Noise | Render each once | `MessageViews.tsx`, `backend/app/agents/parse.py` |
| D-02 | Dashboard | Open findings KPI | Interaction | Medium | Links to non-compliant filter | href | Misleading drill | Link to a findings view or make non-interactive | `DashboardPage.tsx` |
| D-03 | Dashboard, Investigation | Legal entity labels | IA | Medium | `Legal_Entity_07` vs `LE2048` vs `LE4023` | Dashboard drill URL, Investigation text | Identity confusion | One display label and one code everywhere | `DashboardPage.tsx`, `MetricInvestigationPage.tsx`, `backend` label mapping |
| S-01, R-01 | Register, Summary, Preview, Investigation | Titles | IA | Medium | IDs only, API has no name | Payload keys | Hard to scan | Show ID plus family or PD id when present; do not invent names | `RegisterPage.tsx`, `MetricSummaryPage.tsx`, `PageHeader` |
| S-02 | Summary | Breakdown tabs | Visual | Medium | Raw keys as labels | DOM text | Unprofessional | Map keys to labels | `MetricSummaryPage.tsx` |
| S-03, DF-02 | Summary, Definitions | Formula text | IA | Medium | Raw formula repeated | DOM | Redundant, technical | Single owner in Definitions; Summary links to it | `MetricSummaryPage.tsx`, `DefinitionsPage.tsx` |
| G-02 | All | Typography | Visual | Medium | 9 font sizes, min 10 px | Audit script `fonts` | Inconsistent scale | Adopt the type scale in section E | `styles/tokens.css`, `components.css`, `pages.css` |
| G-03 | All | Tokens | Consistency | Medium | `DashboardPage.css` defines `--dash-*` palette and 15 px radius separate from `tokens.css` | Source | Two design systems | Fold into `tokens.css` | `DashboardPage.css`, `tokens.css` |
| G-01 | Shell | `V2Shell`, sidebar | Responsive | Medium | Top bar 157 to 172 px (252 px on Agent) at 768 and below | iframe geometry | About 20% of phone height lost | Compact top bar with menu, move Recent into Agent | `shell/V2Shell.tsx`, `styles/pages.css` |
| I-08 | App Investigation | Metrics tables | Responsive | Medium | Tables scroll internally at every width | `tbl[false,true]` | Content hidden | Responsive table (stacked rows) | `ApplicationInvestigationPage.tsx`, `components.css` |
| R-03 | Register | `MenuSelect` | Accessibility | Medium | `listbox` with checkbox children | DOM | Screen-reader mismatch | Use `menu` with `menuitemcheckbox` or real options | `components/MenuSelect.tsx` |
| R-05 | Register | Preview actions | Visual | Medium | Two filled primaries | Screenshot | Hierarchy unclear | One primary (Open Summary), others secondary | `RegisterPage.tsx` |
| D-04 | Dashboard | Card copy | IA | Medium | Excess fine print | DOM text | Clutter | Keep one line per card; move detail into tooltips and Definitions | `DashboardPage.tsx` |
| D-06 | Dashboard | `LineChart` | Visual | Low | Grid lines unlabelled | Screenshot | Cannot read values | Add y labels and last-value label | `charts/Charts.tsx` |
| A-03 | Agent | Conversation title | Visual | Low | Truncation without ellipsis | DOM h1 | Looks broken | CSS ellipsis, full title on hover | `AgentPages.tsx`, `pages.css` |
| R-04 | Register | Definition links | Accessibility | Low | 24 identical names | Snapshot | Poor navigation | Name by metric id | `RegisterPage.tsx` |
| G-04 | All | Targets | Accessibility | Low | 15 (dashboard), 28 (register) controls under 32 px | Audit script | Mis-taps | Minimum 32 px | `components.css` |
| I-07 | App Investigation | History | Visual | Low | Strip plus duplicate list | DOM | Redundant | Strip only, list on demand | `ApplicationInvestigationPage.tsx` |
| DF-01 | Definitions | Page | IA | Low | 5,799 px with no navigation | Geometry | Hard to find a rule | Anchor index | `DefinitionsPage.tsx` |
| AR-01 | Architecture | Walkthrough copy | IA | Low | "Data Quality" wording | DOM | Stale | Reword for this product | `features/architecture/*` |
| D-01 | Dashboard | Header action | UX | Low | Label "Ask about this view" | DOM | Inconsistent | `Ask Agent` | `DashboardPage.tsx` |

## D. Content decisions

Retain:
- Dashboard KPIs, Compliance mix, Testing distribution, Movement and attention, trend, org concentration, all existing drill-downs.
- Metric Register discovery controls, RAG pills, sparklines, Preview as a centred drawer (bottom sheet on phones).
- Metric Summary calculation, numerator and denominator, history, distributions.
- Investigation Path to Green, contributors, affected applications, honest "proposal, not done" wording.
- Architecture as is. Definitions content.
- Agent landing, composer, context rail, Analysis and Data Explorer response renderers.

Remove:
- The interactive `AgentAnalysisPanel` (composer, polling, follow-up, state label) from Investigation.
- The duplicated History list, the duplicated "Tests" card text, the repeated "923 applications reporting" sentence.
- Raw parser warnings from user view.
- The Data Explorer duplicate intent and duplicate SQL block.

Consolidate:
- One set of design tokens (merge `--dash-*` into `tokens.css`).
- One formula explanation (Definitions only).
- One "Ask Agent" component and label across pages.
- One display identity for legal entities.

Move:
- The Prepared Analysis text to a read-only section below Path to Green on Investigation, with as-of metadata.
- Long lists (affected applications, legal entities) behind View all.

Show on demand only:
- Owner names, formula detail, coverage sentence, Context rail on tablet and phone.

Interactions to redesign:
- Preview "Chat with Agent": navigate to `/agent`, rail shows context, user picks Agent.
- MenuSelect semantics and keyboard behaviour.
- Responsive tables on Application Investigation.
- Mobile shell (compact top bar).

## E. Shared design system recommendations

- Typography: adopt a six-step scale (12, 13, 14, 16, 20, 28 px). Retire 10, 10.5, 11, 11.5, 12.5 px. Mono is for IDs and numbers only, with tabular figures.
- Spacing: use the existing `--s-*` scale (4, 8, 12, 16, 20, 24, 32). Remove literal paddings in page CSS.
- Colours: keep the existing neutral plus blue accent (`--accent`). Data colours stay RAG only. Remove `--dash-*` duplicates.
- Cards: one radius (`--r-card` 12 px, `--r-tile` 16 px for KPI), one shadow (`--e-2`), one header pattern (title left, optional segmented control right).
- Inputs and dropdowns: a single `MenuSelect` and segmented control, 36 px height, proper roles.
- Filters: one scope bar. Register adds only search, sort, RAG and one "More" popover.
- Buttons: one primary per surface; secondary outline; quiet text button. Minimum 32 px height.
- Modals: Preview is the only drawer; centred in the content area, 480 to 520 px, Escape and focus return.
- Tables: one table component with stacked-row mode below 720 px.
- Charts: shared `BarList` and `LineChart`, responsive width, optional value labels.
- Status: one `RagPill` and `StatusChip`; one tone mapping.
- Loading, error, empty: one pattern each; an as-of note instead of warning banners for packaged data.
- Agent conversations: one workspace shell (picker, thread, composer, context rail) rendered for all three routes.

## F. Offline-first coverage (verified in source)

Dashboard has packaged fallbacks only for overview, trends, testing, org contribution, risk distribution and applications, and only for the unfiltered latest month (`portfolio/fallback.py`, `_require_packaged`). These have no packaged fallback (`_no_fallback`, `_unsupported`, or `fallback_fn=None`): filters, compliance distribution, other attribute distributions (legal entity, tier), data coverage, Metric Register, Preview, Summary, Trend, Breakdowns, metric applications, application detail, application history, both Investigations. Investigation bundles in `fallback_assets/v2/investigations/` cover six metrics only.

## G. Unverified areas and blockers

- Pixel screenshots at 1440, 1366 and 1280 px (embedded browser limit); layout verified by geometry.
- Follow-up message send (not allowed by scope); recovery after reload verified.
- Live-chat-unavailable state (Snowflake was up).
- Live keyboard Tab traversal and visible focus (the embedded browser did not move focus into the document); source has a global `:focus-visible` rule (`base.css`).
- Reduced-motion: rules exist in `components.css` (`.working`), `architecture.css` and `DashboardPage.css`; there is no global rule.
- Colour contrast was not measured with a tool.
- Preview behaviour at 1280 and 1366 px was not individually measured.
