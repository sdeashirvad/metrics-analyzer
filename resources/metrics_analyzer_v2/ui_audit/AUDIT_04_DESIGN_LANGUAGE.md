# Audit 04 — Design language

Comparison of `resources/Metrics Analyzer proposed design.html` (seven screens, shared CSS) with `frontend/src/v2`. Source was not modified. No live browser pass.

The design file is a board of seven screens: Dashboard, Triage, Metric register, Metric detail, Application investigation, Analyst agent, Data agent. Shared CSS is identical on every screen. Tokens, type, cards, chips, tables, drawers, and chat chrome are what make the product look like one product.

No Critical gaps. The shell, type scale, and color tokens are in the implementation. The gaps below are places where a designed pattern is missing or visibly weaker.

## Highest-severity missing pieces

1. **High.** Register preview is a weaker substitute for the design’s concise row preview. The three agreed actions are present; the Preview control and the short summary are not.
2. **High.** Filters are open multi-select listboxes. The design uses compact closed selects in a glass toolbar.
3. **High.** Dashboard replaces the 12-month compliance mix and the designed card set with a single-month bar and a flatter attention list.
4. **High.** Metric detail drops the status-mix chart, test funnel, and division-by-month heatmap.

## Register preview verdict

The design **does** have a concise metric-row preview. It does **not** use the labels “Details”, “Investigation”, and “Talk to Agent”.

On screen 3, *Metric register with context preview*:

- Each row ends with a **Preview** button. The selected row reads **Previewing** and uses `tr.sel`.
- A right-hand `aside.drawer` (`aria-label="Context preview"`, 380px, sticky) shows an eyebrow “Context preview”, the metric id, a status chip, two numbers (rate and failed tests), a sparkline, and a short “Included in context” checklist.
- The drawer footer has three actions: **Open detail**, **Data agent**, and **Open in Analyst**.

The agreed product actions replace those three labels. They are **Open Summary/Details**, **Open Investigation**, and **Chat with Agent** (context review, then an unselected choice of Analysis & Investigation or Data Explorer). Those labels are not a gap.

The implementation in `features/register/RegisterPage.tsx` exposes the product actions, and only a weaker preview:

- There is no Preview button. The whole `<tr>` calls `onClick` to set `?preview=`.
- `.table-wrap tr { cursor: pointer }` in `styles/pages.css` is the only hint. The row is not a button, has no accessible name, and has no keyboard handler.
- The drawer is the right component (`drawer sticky`) and its footer does contain the three product actions, stacked full width.
- The body is a longer stats panel (rate, applications, four compliance lines, movement, definition, flags). It does not show the design’s status chip, failed-test figure, or sparkline. Family is hardcoded “Not available”.
- Context checkboxes live inside the Chat with Agent dialog (`features/agent/ChatWithAgent.tsx`), which matches the product decision that review happens when chat starts. Their absence from the drawer is not a gap. The drawer still fails the concise summary.

## Narrow layout in the design

Present, and limited:

- `@media (max-width: 1100px)`: `.g4` becomes two columns; `.g-main` and `.g3` become one column.
- `@media (max-width: 640px)`: `.g4` and `.g2` become one column; `.content` padding becomes `20px 16px 40px`.
- `.app`, `.page-header-row`, `.toolbar`, and the register split use `flex-wrap`. The register split is `display:flex; gap:20px; flex-wrap:wrap`, the table is `flex:1 1 640px`, and the drawer is `width:380px; flex:none`, so the drawer drops under the table when 640px + 380px do not fit.
- `.table-wrap` scrolls horizontally.
- There is no hamburger, no collapsing sidebar, and no rule that caps the 380px drawer at `100%`. Agent screens use an inline grid (`1fr` + `320px`) and do not add their own breakpoint.

`styles/components.css` keeps both media queries and the wrapping split. `styles/pages.css` adds a stronger rule at 800px: the sidebar becomes a full-width bar and primary nav wraps in a row. Conversation layout uses `.g-main`, so it stacks at 1100px. Agent choice cards stack at 720px. Those are stronger than the design.

Remaining narrow gaps are the fixed 28px env bar, the 380px drawer with no `max-width`, and the tall multi-selects, listed below.

## What the implementation already kept

- **Tokens and type.** `styles/tokens.css` and `styles/components.css` carry the design palette, ink, hairlines, provisional amber, accent, mono numerals, 14px body, 24px h1, 11px uppercase labels, card radius 12, KPI radius 16, shadows `--e-2` / `--e-3`, and the canvas tint.
- **Shell.** Brand mark, “Metrics Analyzer”, “Application compliance intelligence”, primary nav with icons, Agent “New” chip, Architecture link, utility nav, Policy Control Office footer, glass sidebar, env dot. Triage is omitted on purpose. Dashboard is `/`. Earlier release is an extra footer link to `/legacy`.
- **Page chrome.** Eyebrow, subtitle, crumbs, segmented controls (`.seg`), glass toolbar, cards, KPI tiles, bar rows, sparklines, stacked bar colors, status chips (where used), provisional dashed tags, callouts, tables, selected-row tint, drawer, chat bubbles, avatars, dark code block, composer, suggestion pills, context chips.
- **Dashboard pieces that survived.** Provisional callout, reporting / non-compliant / no-test tiles, movement pair, org and legal-entity bars, coverage figures, “Ask about this view”.
- **Register pieces that survived.** Search, denominator filter, sparkline column, selected row, right drawer, three product actions, Chat with Agent review then an unselected agent choice.
- **Metric and application pieces that survived.** Provisional rate labelling, denominator labelled provisional, back crumbs, history strip with hatched unobserved months (`StatusStrip`), owner names hidden until requested, application status chips, peers labelled provisional.
- **Agent pieces that survived.** Two distinct agents with short descriptions, portfolio context when no metric is selected, seeded context chips, follow-up suggestion pills when the API returns them, SQL in `.code`, result table, export link, read-only / row-limit messaging in the data path.
- **Responsive rules** listed above, including the extra sidebar stack.
- **Architecture** is a real page at `/architecture` with its own diagram and walkthrough. The design only has a nav item, so that page is not a missing screen.
- **Definitions** uses the same cards, etags, and provisional tags. The design’s utility link is “Glossary & conventions” and has no screen.

## Not gaps

- No Triage page or nav item. Attention filters on the dashboard are the intended home for that information. The visual weakening of that transfer is gap D2.
- Architecture stays at `/architecture`.
- Register actions are Open Summary/Details, Open Investigation, and Chat with Agent.
- Chat reviews context, then offers Analysis & Investigation and Data Explorer with neither pre-selected, including from `/agent` with portfolio context.
- `/investigate/metrics/:metricId` and `/investigate/applications/:eonId` both exist. The metric investigation page tells the reader to choose an application.
- Provisional rates, denominator variants, and derived groups are labelled provisional.
- `family: null` and `FAMILY_NOT_AVAILABLE` are data. Inventing family segments would be wrong. How the empty family is drawn is gap R3.

---

## Must-fix design gaps

### R1. Register row preview

- **Screen/component:** Metric register row and context drawer.
- **Observation:** The design’s preview is a named Preview / Previewing control plus a short drawer (status, rate, failed tests, sparkline). The implementation opens the drawer by clicking the row. The drawer then shows a long definition and count list. The three product actions are real buttons in the footer.
- **Severity:** High
- **Category:** Interaction
- **Evidence:** Design screen 3, row button and `aside.drawer` versus `features/register/RegisterPage.tsx` (`PreviewDrawer`, row `onClick`) and `styles/pages.css` (`.table-wrap tr`, `.drawer-foot.actions`).
- **Impact:** The signature “preview, then act” moment is easy to miss, and it looks like a data dump beside the table. Keyboard users cannot open it.
- **Recommendation:** Put a Preview button on the row, label the open state, and keep the drawer to a short summary (rate, failed tests from `testing`, sparkline, one status chip) above the three actions. Make the control a `<button>` with an accessible name.
- **Scope:** `RegisterPage.tsx` and the drawer footer layout in `pages.css`. Do not rename the three actions back to the mock’s “Data agent” / “Open in Analyst”.

### R2. Preview is mouse-only

- **Screen/component:** Register table row.
- **Observation:** The row handler is `onClick` on `<tr>` with no `tabIndex`, no key handler, and no role. Focus never lands on the preview action.
- **Severity:** High
- **Category:** Accessibility
- **Evidence:** Design screen 3 uses a `<button class="btn btn-sm">`. Implementation is the `<tr onClick>` in `RegisterPage.tsx`.
- **Impact:** The drawer, and therefore Summary, Investigation, and Chat, are unavailable from the keyboard on this page.
- **Recommendation:** Same button as R1. Leave other tables’ rows as normal table rows.
- **Scope:** Register table only.

### F1. Filter controls

- **Screen/component:** Scope bar and register toolbar, used on Dashboard, Register, metric summary, and both investigation pages.
- **Observation:** The design’s filters are closed one-line `.select` controls with an uppercase label and a chevron, sitting in a short glass bar (Month, Bank group, Org hierarchy / BU hierarchy, plus the ask pill). The implementation renders native `<select multiple size={5}>` listboxes for org, legal entity, tier, risk, and lifecycle, so the toolbar is a stack of tall boxes. Register adds another multi-select for denominator. Compact mode hides them behind `<details>`, and the open state is the same listboxes.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Design `.toolbar`, `.field`, `.select` on screens 1–5 versus `components/ScopeBar.tsx` and the denominator `<select multiple>` in `RegisterPage.tsx`. `.select` exists in `components.css` and is unused by these controls.
- **Impact:** Every analytical page loses the design’s density. On a narrow viewport the listboxes dominate the screen. The 640px padding change cannot recover that.
- **Recommendation:** Use closed single-line controls that match `.select`. Open a menu or a compact panel for multi-value choices. Keep Business org / Bank group as the segmented control that already exists.
- **Scope:** `ScopeBar.tsx` and the register denominator field. Applies everywhere `ScopeBar` is mounted.

### D1. Dashboard compliance mix

- **Screen/component:** Dashboard, “Compliance mix by month”.
- **Observation:** The design’s main chart is a 12-month stacked mix (compliant, non-compliant, pending, not applicable) with a coverage caption. The implementation draws one month as a `StackedBar` plus a text list. A line of non-compliant share sits in a lower card.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Design screen 1, `role="img"` stacked months, versus `features/dashboard/DashboardPage.tsx` (`StackedBar` fed by `getComplianceDistribution`) and `components/charts/Charts.tsx`. `PortfolioTrends` has a monthly non-compliant share and row count, not a four-status mix. `ComplianceDistribution` is one month.
- **Impact:** The page reads as a set of counts, which is the opposite of the design’s “read the mix next to coverage” composition.
- **Recommendation:** Make the monthly series the primary chart. A four-status stack needs a monthly status mix the current compliance payload does not include; until that exists, the trend series should occupy this card, with the one-month stack as the legend for the latest month.
- **Scope:** `DashboardPage.tsx` and `Charts.tsx`. Do not add a Triage route to compensate.

### D2. Dashboard card set and attention list

- **Screen/component:** Dashboard movement, concentration, coverage, and ask cards. This is also where triage information was supposed to land.
- **Observation:** The design pairs the mix chart with a movement card (provisional tag, two big numbers, three newest breaches as titled rows with red chips, and a quiet link onward). Below that: concentration bars, a legal-entity card with an All / bank segment, a coverage tile with a large number and a stack bar, and an “Ask the agent” card with three starter questions. The implementation keeps movement numbers and org/legal bars, then uses a flat attention list (name, id, movement word, a count) with no status chips. Coverage is a definition list. Starter questions are absent. The ask action is only the header pill.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Design screen 1 sections “Movement”, “Where it concentrates”, “Legal entities”, “Coverage”, “Ask the agent”, and screen 2’s grouped queue (page omitted on purpose). Implementation is the rest of `DashboardPage.tsx` (`AttentionList`, `OrgCard`, `LegalEntityCard`, coverage `dl`).
- **Impact:** Attention, which replaces triage, does not look like the designed queue. The bottom of the dashboard does not match the top.
- **Recommendation:** Render attention rows with the same title, fine line, and status chip as the design’s list. Use a stack bar beside the coverage counts. Put two or three starter questions on the dashboard ask card. Keep the ask action in the header as well. Do not add a Triage page.
- **Scope:** `DashboardPage.tsx`. Bank segmentation can stay in the scope bar once F1 is compact; the card does not need a second bank control.

### M1. Metric detail charts

- **Screen/component:** Metric summary (`/register/:metricId`), and the same chart language is missing on metric investigation.
- **Observation:** The design’s metric page is a rate-and-status-mix chart (12 / 6 month segment), a three-column test funnel (status, result, compliance) in proportional colored blocks, and a division-by-month heatmap. A right rail holds the provisional definition, two starter questions, and largest contributors. The implementation has a single rate line (`MetricTrendCard`), a calculation list, a one-dimension bar breakdown, and an applications table. Failed-test rate and open findings are not headline tiles. There is no 6 / 12 toggle, funnel, or heatmap.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Design screen 4, “Rate and status mix”, “Test funnel · Oct 2026”, “Division by month”, `.heat`. Implementation: `features/metric/MetricSummaryPage.tsx`, `features/metric/MetricTrendCard.tsx`, `features/investigation/MetricInvestigationPage.tsx`.
- **Impact:** Metric detail is the design’s analytical screen. It currently looks like a form of KPIs and tables, so it does not match Dashboard or the register.
- **Recommendation:** Draw the funnel from test status, result, and compliance counts already represented on these pages. Keep the rate line, and add the status mix beside it when a monthly mix exists. Use `.heat` for division-by-month when that series is available. Put starter questions in the rail next to Chat with Agent.
- **Scope:** Metric summary first, then metric investigation so the two metric routes share one chart language.

### S1. Status is plain text in tables

- **Screen/component:** Register attention is covered in D2. Here: metric application tables, metric investigation applications, application “Metrics this month”.
- **Observation:** The design renders compliance and test result as `.chip.red`, `.chip.amber`, `.chip.green`, and hatched `.chip.na`, usually with the small dot. Those tables in the implementation print `labelOf(...)` as body text. Application investigation does use chips in the page header.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Design screens 2, 4, and 5, chip cells. Implementation tables in `MetricSummaryPage.tsx`, `MetricInvestigationPage.tsx`, `ApplicationInvestigationPage.tsx`. Chip CSS is already in `components.css`.
- **Impact:** Status color, which is the design’s legend, appears on some headers and disappears in the tables under them.
- **Recommendation:** Use the existing chip classes for compliance status, test result, and movement in these tables. Include the dot the design draws with `chip i` when the chip is a status.
- **Scope:** The three tables above and the dashboard attention list from D2. Do not invent colors outside the token set.

### A1. Agent conversation chrome

- **Screen/component:** Analyst and Data conversation, `/agent/:agentKey/:conversationId`.
- **Observation:** The design’s thread sits in a card with a “Grounded in” chip bar, a centred callout, structured sections (Analysis, Chart, Data, Hypothesis · not established), a chart inside the analyst bubble, syntax-colored SQL, and a row of actions (Pin, Save as report, Copy as markdown, Hand to Data agent). The data bubble adds “Understood as”, Edit / Run again, Export CSV / Copy, and “Analyse this result”. A sticky rail holds grounding checkboxes, pinned evidence, ground rules, queryable tables, guardrails, and query history. The implementation has bubbles, avatars, a composer, suggestion pills, plain SQL in `.code`, a result table, and a read-only Context card. `.code .k/.f/.s/.c` are unused. There is no in-bubble chart, no section labels, and no action row. Agent switching in the design is a segment at the top of both agent screens; the conversation page has no equivalent. The unselected choice on the way in is the product decision and stays.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Design screens 6 and 7 versus `features/agent/AgentPages.tsx` (`ConversationPage`) and `features/agent/MessageViews.tsx` (`QueryBlock` writes `query.sql` as plain text).
- **Impact:** Once a conversation starts, Analyst and Data look like the same generic transcript. The design uses color, a chart, and the code block to tell them apart.
- **Recommendation:** Keep the choice step as it is. In the transcript, add the grounded-in chip bar, section labels, syntax coloring with the existing `.code` classes, and the data-agent result actions that already have API support (copy and export). Add an in-bubble chart only when the analysis payload includes a series. A live pin/save/hand-off row needs product support; until then, do not draw dead buttons.
- **Scope:** `MessageViews.tsx` and the conversation layout in `AgentPages.tsx`.

### N1. Env bar clips

- **Screen/component:** Shell environment bar.
- **Observation:** The design bar is 28px tall and holds one short dataset line. The implementation uses the same fixed height and puts a long status string in it (source, version, month, both agent states), plus a retry button on error.
- **Severity:** Medium
- **Category:** Responsive
- **Evidence:** Design `.env-bar` versus `shell/V2Shell.tsx` and `.env-bar` in `components.css` (`height:28px`, padding `0 32px`).
- **Impact:** On a laptop-width window the status overflows the bar or collides with the sidebar. The 800px rule only changes horizontal padding.
- **Recommendation:** Let the bar grow and wrap (`min-height: 28px; height: auto`) and allow the text to wrap. Keep the green or amber dot.
- **Scope:** `components.css` `.env-bar` and, if needed, the status string in `V2Shell.tsx`.

### N2. Drawer wider than a phone

- **Screen/component:** Register drawer.
- **Observation:** The design wraps the drawer under the table and still sets `width: 380px; flex: none` with no `max-width`. The implementation copies that. Below roughly 400px the drawer is wider than the viewport. The 640px rule does not mention `.drawer`.
- **Severity:** Medium
- **Category:** Responsive
- **Evidence:** Design screen 3 inline split and `.drawer` in the shared CSS. Implementation `.split` and `.drawer` in `pages.css` / `components.css`.
- **Impact:** The preview, which is the register’s main action, overflows on a narrow window.
- **Recommendation:** `width: min(380px, 100%)` on `.drawer`, and let `.drawer-foot.actions` stay stacked only when the drawer is full width.
- **Scope:** `components.css` `.drawer`. The wrap behavior can stay.

---

## Optional polish

### R3. Dead Family column

- **Screen/component:** Register table and preview drawer.
- **Observation:** The design’s family segment (All 24, Family 01, …) and Family column depend on family names. The API types `family` as `null` and defines `FAMILY_NOT_AVAILABLE`. The table still has a Family column, and every row, the drawer, and the metric header say “Not available” next to a second “Not available” tag.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design screen 3 header segment and Family column. `api/types.ts` `RegisterMetric.family: null`. `RegisterPage.tsx` and `MetricSummaryPage.tsx` hardcode the string.
- **Impact:** A designed column becomes repeated empty noise. Building fake families would be worse.
- **Recommendation:** Drop the Family column and the header segment while family is null. One flag line is enough when `FAMILY_NOT_AVAILABLE` is present.
- **Scope:** Register and metric header copy only.

### R4. Failed-test column omitted

- **Screen/component:** Register table.
- **Observation:** The design’s columns are Metric, Family, Rate, Failed tests, Apps, 12 months, Preview. The implementation shows Metric, Family, Applications, Rate, Non-compliant, Denominator, Trend. `RegisterMetric.testRows` is on the row and is not displayed. The 12-month sparkline is kept.
- **Severity:** Low
- **Category:** Functional
- **Evidence:** Design screen 3 table head. `RegisterPage.tsx` columns. `RegisterMetric.testRows` in `api/types.ts`.
- **Impact:** The table emphasizes denominator and non-compliant counts and loses the design’s failed-test reading, which the preview was also meant to show.
- **Recommendation:** Add a failed-test figure from `testRows` when R1 rebuilds the row. Keep denominator and the provisional tag; that part is an agreed product decision.
- **Scope:** Register table.

### R5. Pointer cursor on every table

- **Screen/component:** All `.table-wrap` tables.
- **Observation:** `pages.css` sets `cursor: pointer` on every wrapped row. Investigation and metric tables are only partly clickable, through links in one cell.
- **Severity:** Low
- **Category:** Interaction
- **Evidence:** `styles/pages.css` `.table-wrap tr`. Design uses a button on register rows and ordinary rows elsewhere.
- **Impact:** Rows look clickable when they are not.
- **Recommendation:** Remove the global rule. The Preview button from R1 carries the cursor.
- **Scope:** `pages.css`.

### D3. Hero rate versus hero count

- **Screen/component:** Dashboard KPI row.
- **Observation:** The design’s second tile is a 32px provisional compliance rate. The implementation’s four tiles are applications reporting, non-compliant count, no completed test, and open findings. Non-compliant share is a secondary percentage and a lower line chart, and it is labelled provisional. That labelling is the agreed behavior.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design screen 1 KPI “Compliance rate”. `DashboardPage.tsx` KPI grid. `PortfolioOverview` exposes `nonCompliant.share`, not a separate compliance-rate field.
- **Impact:** The number the design treats as the headline is visually secondary. The share is still on the page.
- **Recommendation:** If D1 puts the monthly series first, give the latest provisional share the same 32px KPI treatment beside the count. Do not relabel share as a confirmed rate.
- **Scope:** Dashboard KPI row.

### A2. Ask control has no icon

- **Screen/component:** Ask / Chat with Agent buttons.
- **Observation:** The design’s `.ask` pill includes a 15px spark icon. `ChatWithAgentButton` renders text only (“Ask about this view”, “Chat with Agent”). The CSS for `.ask svg` is already there. Nav icons are in place.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design `.ask svg` and the header buttons on screens 1, 4, and 5. `features/agent/ChatWithAgent.tsx`.
- **Impact:** The primary action is the right gradient pill and is slightly plainer than the design.
- **Recommendation:** Reuse the Agent nav spark inside the ask button.
- **Scope:** `ChatWithAgentButton`.

### A3. Review sheet versus in-page composer

- **Screen/component:** Chat with Agent dialog.
- **Observation:** Context review is a full-height right sheet (520px). The design reviews context in the register drawer and then uses the in-page composer (placeholder, context chip, Send). The sheet does use context chips, checkboxes, agent cards with the blue and teal top borders, and the ask button. The product decision requires review before an unselected choice, so the sheet is a valid place for that step.
- **Severity:** Low
- **Category:** Interaction
- **Evidence:** Design screens 3, 6, and 7 composer. `components/present.tsx` `Dialog` and `.dialog` in `pages.css`. `ChatWithAgent.tsx`.
- **Impact:** The step works and looks related, and it does not yet feel like the conversation surface the design shows after the choice.
- **Recommendation:** After the choice is made, the conversation page (A1) is the surface to align. Leave the unselected cards as they are.
- **Scope:** Polish only if A1 is done.

### A4. Avatar label

- **Screen/component:** User avatar in the transcript.
- **Observation:** The design avatar is a 30px tile with initials. The implementation writes “You” in that tile.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design screen 6 `av-u` “AR”. `AgentPages.tsx` avatar text “You”. `.avatar` is 30×30 at 12px.
- **Impact:** The user tile is cramped next to the single-letter agent tiles.
- **Recommendation:** Use one letter, or widen only the user tile.
- **Scope:** `ConversationPage`.

### X1. Motion tokens are unused on the shell

- **Screen/component:** Shared chrome.
- **Observation:** The design defines `--ease` and does not apply it to nav, buttons, or the drawer. The implementation adds `--t-control` and `--t-panel` and uses them on the architecture diagram, including `prefers-reduced-motion`. Shell hovers remain instant, which matches the design CSS.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design `:root --ease` with no `transition` on `.btn` or `.side-nav`. `styles/architecture.css` transitions. `tokens.css`.
- **Impact:** Architecture feels animated and the rest of the app does not. That split is already how the design file is written.
- **Recommendation:** Optional 160ms hover on nav and buttons, disabled under `prefers-reduced-motion`. Not required for cohesion.
- **Scope:** `components.css` only if a later pass wants it.

### X2. Small copy differences

- **Screen/component:** Page titles and utility nav.
- **Observation:** Register h1 is “Metrics” (eyebrow “Metric register”); the design h1 is “Metric register”. Utility nav says “Definitions & conventions”; the design says “Glossary & conventions”. Dashboard subtitle is “Portfolio counts…”; the design subtitle is “One population of applications, tested against 24 metrics in 6 families.” The family half of that sentence cannot be shown while family is null.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Design screens 1 and 3 headers and the utility nav. `RegisterPage.tsx`, `DashboardPage.tsx`, `V2Shell.tsx`, `DefinitionsPage.tsx`.
- **Impact:** Titles are close enough to scan. The register h1 is the one that drifts.
- **Recommendation:** Use “Metric register” as the h1. Keep “Definitions & conventions” if that is the page name.
- **Scope:** `PageHeader` title on the register.

### X3. Export page control

- **Screen/component:** Register toolbar.
- **Observation:** The design toolbar has “Export page”. The register page has no export control. Data-agent results can export from `MessageViews.tsx`.
- **Severity:** Low
- **Category:** Functional
- **Evidence:** Design screen 3 toolbar. `RegisterPage.tsx` has no export action.
- **Impact:** A secondary toolbar action from the mock is absent. It is not part of the preview pattern.
- **Recommendation:** Add it only if a register export already exists in the API.
- **Scope:** Register toolbar.

---

## Screen checklist

| Design screen | Implementation | Design language |
| --- | --- | --- |
| Shared chrome and CSS | `V2Shell.tsx`, `tokens.css`, `components.css`, `base.css` | Kept, with N1, N2, F1, X1 |
| 1 Dashboard | `DashboardPage.tsx` | D1, D2, D3, F1 |
| 2 Triage | No page, on purpose | Useful visuals belong in D2, not a new route |
| 3 Metric register | `RegisterPage.tsx` | R1–R5, F1 |
| 4 Metric detail | `MetricSummaryPage.tsx`, `MetricTrendCard.tsx` | M1, S1 |
| 5 Application investigation | `ApplicationInvestigationPage.tsx` | History strip and header chips kept; S1 for the metrics table |
| Metric investigation (product route) | `MetricInvestigationPage.tsx` | Same chart and chip language as M1 and S1 |
| 6 Analyst | `AgentPages.tsx`, `MessageViews.tsx`, `ChatWithAgent.tsx` | Choice step kept; A1–A4 |
| 7 Data agent | Same agent pages, dataset view | A1 |
| Glossary link | `DefinitionsPage.tsx` | Cards and provisional tags kept; X2 |
| Architecture nav only | `features/architecture/*` | Out of this design file; not a missing screen |
