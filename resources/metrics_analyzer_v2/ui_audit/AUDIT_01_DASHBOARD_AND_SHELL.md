# Audit 01 — Dashboard and application shell

Live app only: `http://127.0.0.1:5173/` with API `http://127.0.0.1:8080`. No source, style, config, or server changes.

Viewports exercised: 1440×900, 1000×800, 860×900, and 390×844 (device metrics cleared at the end). Interactions: month change, legal-entity filter, Clear, Bank group, Level 2, attention-list Next, and keyboard Tab. Hover styles exist in CSS for nav and buttons; a synthetic Tab does not move focus in this browser, so a keyboard ring was not visually confirmed.

Service check: portfolio calls returned HTTP 200 (`/overview`, `/distributions/compliance`, `/distributions/testing`, `/distributions/legalEntity`, `/org/contribution`, `/status`). The status bar reads **Snowflake · v1-seed20261103 · Oct 2026 · Analysis available · Data available**. No error banner and no retry control appeared, because the page was not in a failed state. Number disagreements below are presentation, not a failed service.

## What looked finished

- Primary nav is Dashboard, Metric register, Agent (with a New chip), Architecture, Definitions & conventions, and Earlier release. There is no Triage item at 1440 or 390.
- Skip-to-content link is present. `:focus-visible` is defined as a 2px accent outline.
- Headline KPIs match the overview contract for October 2026: 923 reporting (−14), 300 non-compliant (32.5%, +2.8 pp), 293 without a completed test (−27), 1,870 open findings (+127). The Non-compliant provisional chip links to `/definitions#PD-08`.
- The provisional callout is visible and the Definitions link works as a route target.
- Month, legal entity, Clear, Bank group, Level 2, and attention pagination all update the URL and the figures after the request finishes.
- At 390px the sidebar becomes a full-width bar, nav labels are not clipped, and the filter lists do not cover the KPI cards.
- The stacked compliance bar uses distinct green, red, amber, and grey segments. Attention rows are readable links with a reason and a count.

The supplied screenshot (sidebar labels clipped, and Legal entity / Super division / Division lists covering the KPI cards) was not reproduced. Hit-testing at 1440, 1000, 860, and 390 found no intersection between the `<select>` lists and the callout or KPI cards. The toolbar wraps and grows. At 1440 the lists end at y=274 and the callout starts at y=349. At 860 the toolbar ends at the callout (both y=492).

## Must fix

### 1. Sidebar wordmark collides

- **Screen/component:** Application shell, brand lockup in the 232px sidebar
- **Observation:** “Metrics” and “Analyzer” stack, and “Application compliance intelligence” starts on the same line as “Analyzer”. The live crop reads **AnalyzerApplication**. `brand-name` is an inline box (x=49, y=20, 56×39) and `brand-sub` is inline (x=49, y=43, 114×35), so the boxes overlap by about 16px. At 390px the sidebar is full width and the two spans sit side by side without that collision.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Element screenshot of `.brand` at the 1440 layout, plus bounding boxes. Desktop nav labels themselves wrap and are not cut off (“Definitions & conventions” is two lines inside a 203px link).
- **Impact:** The product name is unreadable in the shell that is on screen for every desktop page.
- **Recommendation:** Make `.brand-name` and `.brand-sub` block-level inside the 232px sidebar, with the subtitle starting below the name (at least 4px gap). Keep the single-line row only when the brand row is wider than about 280px.
- **Scope:** Component / CSS (`.brand`, `.brand-name`, `.brand-sub`)

### 2. Attention switch clips “Resolved” and forces a horizontal scrollbar

- **Screen/component:** Dashboard, Movement and attention, mode switch
- **Observation:** Five labels (Non-compliant, No completed test, Failed test, Newly non-compliant, Resolved) sit in a segment about 298px wide. Each button wraps to about 69px tall. At 1440 the Resolved button runs from x=1397 to x=1473, past the 1425px client width. `scrollWidth` is 1473. At 390 the same button ends at x=436 against a 390px client width, which is the only horizontal overflow on the phone layout. A clip of the control shows the last label as **Re**.
- **Severity:** High
- **Category:** Responsive
- **Evidence:** Geometry at 1440×900 and 390×844, plus a 440×220 clip of the control at desktop. The 1440 page has a horizontal scrollbar. At 1000px the movement card is full width and the control fits (Resolved right edge 856, client 985).
- **Impact:** One of the five attention modes is not readable, and the whole dashboard can be scrolled sideways.
- **Recommendation:** On a column narrower than about 420px, lay the five modes out as a wrapping group of single-line chips (or a select), with `min-width: 0` on the card and no page-level overflow. Do not let the button row exceed the card padding box.
- **Scope:** CSS / component (`.seg` in the attention card)

### 3. Compliance mix and Testing show two grains as one population

- **Screen/component:** Compliance mix card and Testing card
- **Observation:** The mix bar and legend are metric rows: Compliant 463 (42.2%), Non-compliant 324 (29.6%), Pending 183 (16.7%), Not applicable 126 (11.5%). Those four sum to 1,096, and the percentages sum to 100% of 1,096. The footnote on the same card is application grain: “Applications: 300 non-compliant, 623 not non-compliant, of 923.” The Testing header is application grain (293 without a completed test, 247 with a failed test, 923 reporting) while the rows are metric rows (Test complete 736, No test 168, Test pending 109, Exempt 83) and the result line is “Pass 459 · Fail 273 · Not recorded 4”. 736+168+109+83 = 1,096. Fail 273 is not the same number as 247 applications with a failed test.
- **Severity:** High
- **Category:** Functional
- **Evidence:** DOM text at 1440 after a successful load. `GET /api/v1/portfolio/distributions/compliance` returns `metricRows.byStatus` (1,096) and `applications` `{nonCompliant:300, notNonCompliant:623, total:923}`. `GET /api/v1/portfolio/distributions/testing` returns both `byTestStatus[].metricRows` and `applications`. Both responses are HTTP 200 with empty warnings. The UI turns `notNonCompliant` into the words “not non-compliant”.
- **Impact:** A reader can treat 324 and 300 as a contradiction, and can treat 273 fails as the same thing as 247 applications. The footnote is also hard to say aloud.
- **Recommendation:** Title the bar “Metric rows” and show 1,096 as its denominator. Keep the application sentence, and write it as “300 non-compliant applications · 623 other applications · 923 reporting.” On Testing, label the 736/168/109/83 rows as metric rows and the 293/247 line as applications. Do not place Fail 273 next to “247 with a failed test” without those nouns.
- **Scope:** Component copy / behavior. The API already separates the grains. This is not an API failure.

### 4. Breakdown bars are ranked by count while the caption says share

- **Screen/component:** Where it concentrates, and Legal entities
- **Observation:** The caption is “Share of applications that are non-compliant.” Bar width is `nonCompliantApplications / max(nonCompliantApplications)`, not the share. Super_Division_04 is 65 · 33.5% with a 100% bar. Super_Division_02 is 50 · 36.5% with a 76.9% bar, so the higher share has the shorter bar. Legal entity rows print only the share. Legal_Entity_07 reads 16.7% while the fill is 22.2% (4 non-compliant applications out of a max of 18). The same pattern appears after switching to Bank group and Level 2 (BU_Division_05_03 is 19 · 42.2% and sits below divisions with lower shares and higher counts).
- **Severity:** High
- **Category:** Functional
- **Evidence:** Bar `style.width` compared with `GET /api/v1/portfolio/org/contribution` and `GET /api/v1/portfolio/distributions/legalEntity` (HTTP 200). Level 2 click updated the URL to `orgLevel=2` and rendered BU_Division rows, so the data refresh works.
- **Impact:** The picture ranks volume. The sentence says it ranks rate. Legal entity has no count on the row, so the only number disagrees with the bar.
- **Recommendation:** Either set the fill to `nonCompliantShare` (0–100% of applications in that group) or change the caption to “Non-compliant applications” and print the count on every legal-entity row. If the bar stays relative to the max count, say “length is the count, scaled to the largest group.”
- **Scope:** Component / behavior (bar width binding and caption). API fields for both count and share are present.

### 5. Desktop cards stretch to a blank panel

- **Screen/component:** Compliance mix, and Where it concentrates, above the 1100px breakpoint
- **Observation:** The two-column grid stretches siblings to the same height. Compliance mix content ends 298px into a 941px card, leaving 643px empty. Where it concentrates content ends 376px into a 1,306px card, leaving 930px empty under eight rows. The sibling (attention list, legal-entity list) is what sets the height. Below 1100px the grid is one column and the empty gap drops to about 19px.
- **Severity:** High
- **Category:** Visual
- **Evidence:** `section.card` boxes at 1440×900. A scroll of Compliance mix shows the legend, the footnote, then a large empty white area. At 390px Compliance mix is 334px tall and Where it concentrates is 395px tall.
- **Recommendation:** Use `align-items: start` on `.g-main` (and the concentration/legal-entity row) so a card is only as tall as its content. Keep a shared gap of 16px between rows.
- **Scope:** CSS (`.g-main`, `.g2` / the card grid)

### 6. Filters are always-open native list boxes

- **Screen/component:** Dashboard filter toolbar
- **Observation:** Month and M&A are native `<select>` dropdowns (`appearance: auto`). Super division, Division, Legal entity, Tier, Risk, and Lifecycle are native multi-selects with `size` 4 or 5, so five rows are always open. They are the first controls on the page. At 390px those lists run from about y=510 to y=974, and the first KPI starts at y=1062, below an 844px screen. Tier is 34px wide at 390px. Nothing overlaps the KPI cards; the cost is a long, browser-default form before any number.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Computed `appearance: auto`, `size` 4–5, and boxes at 1440 and 390. Month change to Sept 2026 and legal entity LE2048 both filtered correctly, then Clear restored 923 / 300. The control works. It does not look like part of the KPI system.
- **Recommendation:** Replace each multi-select with a closed field showing “All” or the selection count, opening a checkbox list. Keep Month and M&A as single selects but use the existing `.select` button style so they match Business org / Bank group. On widths under 800px, put the six multi-filters behind one “Filters” disclosure so the first KPI is on the first screen.
- **Scope:** Component / CSS

### 7. Trend axis labels are drawn for a 640px viewBox inside a much smaller box

- **Screen/component:** Non-compliant share chart
- **Observation:** The SVG `viewBox` is `0 0 640 180` and `overflow` is hidden. At 1440 the painted box is 324×200. Axis text “Nov 2025”, “May 2026”, and “Oct 2026” measure about 23–25px wide. “Oct 2026” is placed at viewBox x=612, against the 640 edge. At 860px the SVG is 507px wide and the same labels are still only 35–38×11px.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** `getBoundingClientRect` on the SVG and its `<text>` nodes after scrolling the chart into view, at the 1440 layout and again at 860px.
- **Impact:** The months are hard to read, and the last label is at the clip edge.
- **Recommendation:** Size the viewBox to the rendered width, or set text in screen pixels. Anchor the last label `end` at least 8px inside the plot. Show three labels only when each label has about 64px of room; otherwise show first and last.
- **Scope:** Component / CSS (trend SVG)

### 8. Status month stays on October when the page is September

- **Screen/component:** Top status bar
- **Observation:** After the month control is set to Sept 2026, the KPIs and the mix subtitle change to September (937 reporting, mix “Sept 2026”), but the status bar still says Oct 2026.
- **Severity:** Medium
- **Category:** Functional
- **Evidence:** Select value `2026-09-30`, URL `?month=2026-09-30`, env bar text unchanged. `/api/v1/portfolio/status` reports `latestMonth: 2026-10-31`, so the bar is showing the dataset’s latest month, not the filter.
- **Impact:** The strip and the page disagree about which month is on screen.
- **Recommendation:** Label the strip “Latest month Oct 2026” or, when a month is selected, show the selected month in that strip.
- **Scope:** Component copy

## Optional polish

### 9. Single-page breakdown footer is a bare count

- **Screen/component:** Where it concentrates footer
- **Observation:** With one page the footer is the number 8 (eight super divisions). With Level 2 it becomes “1 / 2 · 16”. The single-page form has no noun.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Footer text before and after Level 2 (`orgLevel=2`, 16 divisions, 8 rows per page).
- **Impact:** An unexplained 8 sits under the list.
- **Recommendation:** Use “8 groups” on a single page, and keep “1 / 2 · 16 groups” when paged.
- **Scope:** Component copy

### 10. “Provisional” runs into the chart note

- **Screen/component:** Non-compliant share subtitle
- **Observation:** Accessible text is “Provisional Gaps are not plotted as zero.” The chip and the sentence have no separator.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Section text at 1440.
- **Impact:** The note reads as one broken sentence.
- **Recommendation:** Put the chip and the sentence in separate inline elements with an 8px gap: “Provisional” then “Gaps are not plotted as zero.”
- **Scope:** Component / CSS

### 11. Keyboard ring on native selects was not confirmed

- **Screen/component:** Shell and filter controls
- **Observation:** CSS sets `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }`. After mouse clicks and scripted `focus()`, `:focus-visible` did not match, and the computed outline style on the month `<select>` was `none`. Synthetic Tab did not move focus, so a real keyboard pass could not be completed. The skip link is positioned off-screen until focus (top: -48px, and `.skip:focus` moves it to 12px).
- **Severity:** Low
- **Category:** Accessibility
- **Evidence:** Stylesheet rule list and `getComputedStyle` on the focused select, nav link, and Ask button. Tab key pressed twice; `document.activeElement` stayed on the select.
- **Impact:** If the native control’s own ring is suppressed, keyboard users get no visible focus on the filters.
- **Recommendation:** After the filters are custom controls, keep the accent `:focus-visible` ring on every button and list. Until then, do not set `outline: none` on `select:focus`.
- **Scope:** CSS

## Not a defect

- No repeated error banners. The page loaded.
- Filter lists overlapping the KPI cards: not present at the widths measured.
- Sidebar nav text clipping: not present. The collision is the wordmark, not the nav labels.
- “623 not non-compliant” is not an API error. The field is `applications.notNonCompliant`. The defect is that the UI prints that name in the sentence.
- Snake_case names (Super_Division_04, Legal_Entity_07, BU_Division_05_02) match the API labels.
