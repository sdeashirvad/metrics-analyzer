# Metrics Analyzer V2 — UI/UX audit summary

Consolidation of the four live audits and the design-language comparison. Product decisions below stay. Each item is deduped across reports. Outcome is updated after the remediation and the browser recheck.

Sources:

- `AUDIT_01_DASHBOARD_AND_SHELL.md`
- `AUDIT_02_METRIC_WORKFLOWS.md`
- `AUDIT_03_AGENTS_AND_ARCHITECTURE.md`
- `AUDIT_04_DESIGN_LANGUAGE.md`
- Visual direction: `resources/Metrics Analyzer proposed design.html`

## Product decisions that stay

- Dashboard is `/`. No Triage page and no Triage nav item.
- Preview is a right-side drawer. Its actions are Open Summary/Details, Open Investigation (metric-scoped; an application opens only when the user picks one), and Chat with Agent (context review, then an unselected choice of Analysis & Investigation or Data Explorer).
- Both investigation routes stay. The UI does not invent an application id.
- Both agents stay distinct and are selectable from `/agent` with portfolio context.
- Provisional metrics stay visible and labelled provisional.
- Architecture stays at `/architecture` with the diagram and the guided walkthrough.
- Legacy stays under `/legacy/*`. Existing `/api/v1/dq/*` and `/api/v1/tr/*` stay backward compatible.

## Consolidated findings

| Id | Severity | Screens | Outcome | What was wrong |
| --- | --- | --- | --- | --- |
| S1 | Must fix | Shell, every page | Fixed | Wordmark and subtitle overlap, so the lockup reads “Metrics AnalyzerApplication” in the 232px sidebar and on the phone bar. |
| D1 | Must fix | Dashboard attention switch | Fixed | “Resolved” is clipped and the page scrolls sideways at 1440px and 390px. |
| D2 | Must fix | Compliance mix, Testing | Fixed | Metric-row counts and application counts are presented as one population. The footnote says “623 not non-compliant.” |
| D3 | Must fix | Where it concentrates, Legal entities, metric breakdown | Fixed | Bars are scaled by non-compliant count and captioned as share. |
| D4 | Must fix | Dashboard cards above 1100px | Fixed | Compliance mix and Where it concentrates stretch to the height of the taller sibling and leave a large empty area. |
| F1 | Must fix | Dashboard, register, metric detail, both investigations | Fixed | Org, legal entity, tier, risk, lifecycle, and denominator filters are always-open native multi-selects. On a phone the first number starts below the fold. |
| R1 | Must fix | Metric register preview | Fixed | No visible Preview control and no keyboard path. The drawer is a long stats sheet. The three actions sit below the first screen at 1440px and below the table at 390px. |
| R2 | Must fix | Register table at 390px | Fixed | The Provisional chip is clipped. Non-compliant, Denominator, and Trend sit in a horizontal scroll with no readable narrow layout. |
| R3 | Must fix | Chat with Agent dialog | Fixed | The context review does not take focus, trap it, or restore it on close. |
| A1 | Must fix | Agent setup composer | Fixed | The message field has no visible box, placeholder, or focus ring. |
| A2 | Must fix | Analysis answer | Fixed | Assistant text shows raw `**asterisks**` and collapsed line breaks. |
| A3 | Must fix | Architecture desktop | Fixed | The sticky walkthrough covers the selected node’s detail. |
| A4 | Must fix | Architecture at 390px | Fixed | After scroll, diagram nodes paint over the sticky navigation and take its clicks. |
| D5 | Material medium | Non-compliant share chart | Fixed | Axis labels are SVG user units inside a 640-wide viewBox, so they shrink and the last month sits on the clip edge. |
| D6 | Material medium | Status bar | Fixed | After the month changes to September the strip still reads as if October is the month on screen. The status payload’s `latestMonth` is October. |
| D7 | Material medium | Env bar | Fixed | A fixed 28px bar holds a long status string. |
| N1 | Material medium | Phone shell | Fixed | The phone bar is a ~309px navigation block, and its translucent background lets the architecture diagram receive clicks. |
| A5 | Material medium | Agent cards | Fixed | “Available” stretches into a full-width bar. Data Explorer loses its teal accent once selected. Setup eyebrow is “Agent” for both. |
| A6 | Material medium | Context checklist | Fixed | One row repeats its title as the description. Checkboxes are the tiny native control. Exact-text prose scrolls sideways. |
| A7 | Material medium | Definitions | Fixed | Provisional is shown twice, and other classes show raw tokens (`assumption`, `documented_rule`, `not_available`). |
| S2 | Material medium | Attention list and metric/application tables | Fixed | Status is plain text where the row already has a status value. Chip styles already exist. |
| M1 | Material medium | Metric summary and metric investigation | Fixed | The metric trend payload includes `complianceRows` per observed month, and the summary and investigation payloads include compliance and test counts. Those charts were missing. |
| R4 | Material medium | Metric summary provisional banners | Fixed | Six full-width amber banners repeat the same kind of provisional notice. |
| P1 | Optional | Concentration footer, chart note, family cell, row cursor, register title, ask icon, “1 rows”, copy feedback, avatar | Fixed | Small unfinished copy and affordances on screens that were already open. |
| M2 | Deferred | Dashboard 12-month compliance mix | Deferred | `PortfolioTrends` is applications, non-compliant share, and row counts. `ComplianceDistribution` is one month. There is no four-status monthly series. The one-month metric-row mix stays, with the grain labelled. |
| M3 | Deferred | Division-by-month heatmap | Deferred | Metric breakdowns are one dimension for one month. No division-by-month series is returned. |
| X1 | Rejected | Dashboard starter questions, triage page, hero-rate swap | Rejected | See rejections. |
| X2 | Rejected | Conversation pin / save / hand-off / in-bubble chart | Rejected | See rejections. |
| X3 | Rejected | Drop the Family column, add a failed-test column, register export | Rejected | See rejections. |
| X4 | Rejected | Phone hamburger, motion tokens, glossary rename, review-sheet redesign | Rejected | See rejections. |

## Must fix

### S1 — Wordmark

Audits 01.1, 02.5, 03.1. The name and subtitle are inline boxes and overlap by about 16px in the sidebar. On the phone they touch, so the line reads “Metrics AnalyzerApplication”.

Fix: stack them as blocks in the 232px sidebar. On the full-width phone bar, put them in one row with an explicit gap so a wrap breaks between the two strings.

### D1 — Attention switch

Audit 01.2. Five nowrap segments sit in the narrow movement column. “Resolved” runs past the viewport at 1440px (`scrollWidth` 1473) and at 390px (ends at x=436).

Fix: wrap the modes inside the card. No page-level horizontal scroll.

### D2 — Two grains, one sentence

Audit 01.3. Compliance `metricRows.byStatus` sums to 1,096. `applications` is 300 / 623 / 923. Testing rows are metric rows; the header counts are applications. Fail 273 is not “247 applications with a failed test.” The UI prints the field name “not non-compliant.”

Fix: label the bar and the test rows as metric rows, and the application sentence as applications. Write “300 non-compliant applications · 623 other applications · 923 reporting.” Do not invent a third grain. The API fields are unchanged.

### D3 — Bar and caption disagree

Audit 01.4. Width is `nonCompliantApplications / max(count)`. The caption says share, so a higher rate can have a shorter bar. Legal-entity rows print only the share, which then disagrees with the fill. The metric breakdown repeats the pattern: the bar is the count and the note is only the rate.

Fix: keep the count scale, say that the length is the count scaled to the largest group, and print the count on every row. The share or rate stays as a second number, not as the bar.

### D4 — Empty stretched cards

Audit 01.5. Above 1100px, grid stretch makes Compliance mix and Where it concentrates as tall as their siblings.

Fix: `align-items: start` on the card grids so a card is as tall as its content, with the existing 16px gap.

### F1 — Compact filters

Audits 01.6, 02.2, 04.F1. `ScopeBar` and the register denominator control render `<select multiple size="4|5">`. Month and M&A use native appearance. At 390px the lists run past the first screen. The stack has no select library.

Fix: closed controls that show All, Latest, Any, or the selection. A positioned popover (fixed, so it is not clipped) holds the choices and a clear action. Hover, focus, selected, disabled, and open states live in the existing CSS. Under 800px the multi-filters stay behind a closed Filters control so the first KPI can sit on the first screen. Search stays an input. Business org / Bank group stays the segmented control.

### R1 — Preview

Audits 02.1, 04.R1, 04.R2. The row is a clickable `<tr>` with no name. The drawer lists family, counts, the formula, and definition notes. Actions were at about y=1059 in a 900px viewport. At 390px the drawer is appended after the table.

Fix: a Preview / Previewing button named with the metric id. The drawer opens on a short summary (rate, failed tests from `testing.fail`, sparkline, application count) and keeps the three agreed actions in the footer, in view on desktop. On a phone the drawer is a bottom sheet, not a block under the table. Focus moves in and returns to the button. Escape closes the top layer only.

### R2 — Register at 390px

Audit 02.3. The table is 754px inside a 358px scroller. The rate cell cuts “Provisional” to “Provisio”.

Fix: a stacked row under the narrow breakpoint, with a label for each value. No overlapping text and no accidental page scroll. With the drawer open on desktop, the table shrinks instead of forcing a sideways page scroll.

### R3 — Chat focus

Audit 02.4. `role="dialog"` is set, but focus stays on the button behind it, so Tab reaches the page. Send sits below a long checklist.

Fix: focus the dialog heading, trap Tab, restore focus on close. The review scrolls, and the agent choice, message, and Send stay in view. Neither agent is preselected. Order stays review, then choice.

### A1 — Message field

Audit 03.2. `.field textarea` sets `border: 0` and a transparent background. Setup has no composer card around it, and `outline` does not show. Send is stretched by the column layout.

Fix: a bordered, filled field with placeholder “Ask about the portfolio”, a 2px focus ring, and a compact Send at the end of the field. The conversation composer keeps its card and gains a placeholder and a focus ring.

### A2 — Markdown

Audit 03.3. The answer is one `<p>`, so `**bold**` and blank lines survive as source. No markdown package is installed.

Fix: a small renderer for paragraphs, bold, lists, inline code, and fenced code. Text is React text, so raw HTML is escaped.

### A3 — Walkthrough vs detail

Audit 03.4. `.arch-dock` is sticky at the bottom of the viewport and crosses the detail, including Inputs.

Fix: place the walkthrough in normal flow above the diagram so it does not sit on the detail. It still advances the same steps.

### A4 — Diagram vs navigation

Audit 03.5. At 390px the sidebar is sticky, translucent, and `z-index: auto`. Scrolled nodes and the Experience heading receive the hit test on Dashboard.

Fix: a solid phone bar with a z-index above the page. Diagram clicks no longer land on the nodes when the pointer is over a nav link.

## Material medium

### D5 — Trend axis

Audit 01.7. Labels are drawn in the 640×180 viewBox, so they scale down with the plot.

Fix: draw the line in the SVG and the first, middle, and last month as HTML type under it.

### D6 — Status month

Audit 01.8. `/portfolio/status` reports `latestMonth`. The strip was printing that month as if it were the filter.

Fix: “Latest month Oct 2026”. When the filter is a different month, add “Viewing Sept 2026”. No new status field.

### D7 — Env bar

Audit 04.N1. `height: 28px` clips the long status line.

Fix: `min-height: 28px` and wrapping text. The dot stays.

### N1 — Phone shell

Audits 02.6 and 03.11, together with A4. A hamburger is rejected (X4). The bar is shortened: one scrolling row of links, utility label hidden, footer reduced to Earlier release, brand on one line with a gap.

### A5 — Agent identity

Audits 03.6 and 03.7. The status chip stretches. `.agent-card.is-selected` paints Data Explorer with the analysis blue. Both setup screens use the eyebrow “Agent”.

Fix: chip hugs the word. Data Explorer keeps the teal border and ring. The setup eyebrow names the agent. The landing still preselects nothing.

### A6 — Context checklist

Audits 02.7 and 03.8 and 03.9. The sample row’s summary falls back to the same string as the title. Portfolio trend does the same. The exact-text `<pre>` is `white-space: pre`.

Fix: hide a summary that repeats the title. Display definition-id tokens as PD-01. Larger hit target on the checkbox. Prose wraps. SQL blocks stay a horizontal code scroller.

### A7 — Definition tokens

Audit 03.10. Gold “Provisional” plus a grey `provisional` chip, and snake_case class tokens.

Fix: one human label per card (Provisional, Assumption, Source observation, Documented rule, Not available) and a one-line legend. Provisional items are not hidden.

### S2 — Status chips

Audit 04.S1 and the attention half of D2. The tables already render compliance, test, and movement strings.

Fix: use the existing chip tones for those cells and for the attention row. No new status colors.

### M1 — Metric mix and funnel

Audit 04.M1, limited by the instruction to chart a series only when the current API returns it.

- Metric trend points include `complianceRows` for each observed month. The rate card shows that mix, labelled as metric rows.
- Metric summary `preview.compliance` / `preview.testing`, and metric investigation `observations.compliance` / `observations.testing`, include the status, test-status, and completed-result counts. A three-block chart uses those counts and names the grain.

### R4 — Repeated provisional banners

The metric summary prints one full-width warning per provisional statement (PD-01, PD-02, PD-13, and the rest). They are the same kind of notice.

Fix: one provisional callout that lists the statements. Card-level data errors still have their own retry. A failed request does not invent numbers.

## Optional, included because the screen was already open

### P1

- Concentration footer says “8 groups” (and “1 / 2 · 16 groups” when paged) instead of a bare count.
- The provisional chip and “Gaps are not plotted as zero.” are separate.
- Family shows one “Not available” chip, not the sentence plus the chip.
- The pointer cursor is removed from tables that are not buttons. Register rows use the Preview button.
- Register heading is “Metric register”.
- Ask / Chat with Agent uses the existing spark icon.
- “1 row” / “N rows”. Copy SQL shows Copied or Copy failed.
- The user tile uses one letter so it fits the 30px avatar.
- Internal tool ids in the result line are shown as Query or Analysis.

## Deferred

### M2 — Dashboard 12-month compliance mix

Audit 04.D1. The design’s chart is twelve stacked months of compliant, non-compliant, pending, and not applicable. `GET /portfolio/distributions/compliance` returns `metricRows.byStatus` for the selected month only. `GET /portfolio/trends` returns `nonCompliantShare`, application counts, and `metricRows` per month, not a four-status mix. Drawing that stack would invent the missing statuses. The selected month stays as the labelled metric-row mix. The non-compliant share trend stays the share trend.

### M3 — Division heatmap

Audit 04.M1. Breakdowns are one month and one dimension (`org`, `legalEntity`, and the others). There is no division-by-month matrix. A heatmap would have to invent cells. The breakdown list stays, with the bar labelled as a count.

## Rejected

### X1 — Extra dashboard composition

- Starter questions on an “Ask the agent” card (04.D2). The dashboard does not receive a question list. Writing three prompts would invent them. Ask about this view stays the header action and still opens a context review.
- A Triage route or nav item. Attention on `/` is the home for that list. The audits already record the omission as intentional.
- Replacing a KPI with a 32px “compliance rate” (04.D3). The four tiles are applications reporting, non-compliant applications, no completed test, and open findings. The share is already on the non-compliant tile and on the trend, and it stays labelled provisional.

### X2 — Conversation chrome that has no payload

Audit 04.A1. Pin, Save as report, Copy as markdown, and Hand to Data agent have no action behind them. Agent metadata sets `charts: false`. An in-bubble chart would be a picture without a series. Grounded-in context remains the context card. Bold, lists, and code are A2. Copy SQL and Export stay where the API already supports them.

### X3 — Register columns and export

- Dropping the Family column (04.R3). Family is null and PD-13 says to show that it is not available. The duplicate sentence is removed. The column stays.
- A failed-test column (04.R4). `testRows` does not include the fail result. `testing.fail` is on the preview payload, so the concise preview shows it. Another table column would fight the narrow layout.
- Export page (04.X3). The register has no export API. Data-agent export stays on the result that already supports it.

### X4 — Shell and motion ideas that add a second pattern

- A hamburger (02.6, 03.11). The design has no menu button. A new open/close nav is a second interaction on every page. The phone bar is one solid scrolling row, which also fixes A4.
- Applying unused motion tokens to the shell (04.X1). The design file defines `--ease` and does not transition nav or buttons. Architecture keeps its own motion, including reduced motion.
- Renaming Definitions & conventions to Glossary & conventions (04.X2). The page title is Definitions & conventions.
- Replacing the Chat with Agent sheet with the in-page composer (04.A3). The product decision is a context review and then an unselected agent choice. The sheet stays. The conversation page is the surface after Send.

## Not defects

- Snake_case org labels match the API.
- Filter lists overlapping the KPI cards was not reproduced; the cost was the always-open lists (F1).
- An intermittent “no packaged extract” warning is a service response. The amber callout and Retry stay. The remediation does not paper over a failed payload with numbers.
- No Critical defects in the four audits.

## Browser recheck

Local app at `http://127.0.0.1:5173`, API at `http://127.0.0.1:8080`. Device metrics 1440×900, then 390×844, then cleared with `Emulation.clearDeviceMetricsOverride`. The browser was unlocked after the pass. No page-level horizontal scroll on the routes below (`scrollWidth` matched the layout width: 1425 at the desktop override, 390 on the phone).

### About 1440px

- `/` Wordmark is a column: “Metrics Analyzer” ends at y=38 and “Application compliance intelligence” starts at y=42 (4px gap). Attention “Resolved” stays inside the card. Compliance mix is labelled metric rows (1,096). Applications read “300 non-compliant · 623 other · 923 reporting”, with no “not non-compliant”. Testing names applications and metric rows separately, including completed results Pass 459 · Fail 273 · Not recorded 4. Compliance mix and Where it concentrates size to their content. Eight filters are closed buttons. The legal-entity popover is fixed inside the viewport and is not a permanent list. Selecting Legal_Entity_07 set `?legalEntity=LE2048`.
- `/register` Twenty-four Preview buttons. Opening Preview M340202 puts focus in the drawer. The summary shows rate 44.5%, 42 failed tests (metric rows), 174 applications · Oct 2026, and family not available. Open Summary/Details, Open Investigation, and Chat with Agent are all inside the 900px viewport.
- Chat with Agent: focus lands on the heading. Both agents are unchecked. Send is visible and disabled until a choice and a message exist. Tab stays in the dialog. Escape closes the dialog and leaves the preview open.
- `/register/M340202` One provisional callout, the status-and-testing funnel, and the month mix. One native breakdown select remains (a single closed combobox). No overflow.
- `/investigate/metrics/M340202` Subtitle: “An application is opened only when you choose one.” Application_00694 links to `/investigate/applications/EON743680?metric=M340202`.
- `/agent` Analysis stays blue and Data Explorer stays teal. Available chips hug the label. The saved analysis thread renders **923 applications reported…** as bold text, shows “1 row”, and does not show raw asterisks. The setup message field is a white box with a visible border and placeholder “Ask about the portfolio”. The setup eyebrow reads “Analysis & Investigation”.
- `/architecture` The walkthrough is static and sits above the diagram (dock bottom 284, detail top 756). Next advances to “Step 1 of 9 · Open an investigation” and the node detail stays readable.
- `/definitions` One human status label per card (Provisional, not a second provisional token). No overflow.

### About 390px

- `/` Brand and subtitle sit on one row with an 8px gap, so the line does not read “Metrics AnalyzerApplication”. The nav bar is about 157px, solid white, z-index 30. The first KPI starts at y=542, on the first screen. Filters are behind a closed Filters button. “Resolved” is fully visible. No sideways scroll.
- `/register` Rows are stacked cards. The Provisional chip is fully visible (right edge 359). Preview M340202 opens as a fixed bottom sheet (y=566–836). All three actions are on screen (Chat with Agent ends at y=819). Focus is inside the drawer.
- Chat on the phone covers the viewport, both agents unchecked, placeholder present, Send on screen. Escape closes the dialog and leaves the preview.
- Filters on the metric investigation open extra closed selects, not an always-open list. The legal-entity popover is fixed (y=579–836, height 258, z-index 36) and inside the 390×844 viewport. Escape closes it.
- `/register/M340202`, `/investigate/metrics/M340202`, `/agent`, and `/definitions` do not scroll sideways. The investigation still offers real application links and does not invent an id.
- `/architecture` After scrolling the diagram, `elementFromPoint` on Dashboard returns the Dashboard link. No visible diagram node overlaps the nav bar.

### Tests

`npm test` in `metrics-analyzer/frontend`: 13 files, 57 tests passed. `npm run build`: TypeScript and Vite build succeeded. Backend copy and schema were not changed, so pytest was not run. Both servers were left running.
