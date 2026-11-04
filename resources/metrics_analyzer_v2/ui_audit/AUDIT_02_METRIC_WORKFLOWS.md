# Audit 02 — Metric register, preview, detail, and investigation

Live app only: `http://127.0.0.1:5173` with API `http://127.0.0.1:8080`. No source, style, config, git, or server changes.

Viewports: desktop layout 1440×900, then phone 390×844 (`Emulation.setDeviceMetricsOverride`, cleared at the end). Each width opened the register, a row preview, a metric detail page, and an investigation. The application investigation used a row that was actually listed: Application_00694, `EON743680`, linked as `/investigate/applications/EON743680?metric=M340202`.

Status bar on these screens: **Snowflake · v1-seed20261103 · Oct 2026 · Analysis available · Data available**.

## What already works

- Search updates the URL and the rows. `q=M340` left one row, M340202. Clearing search restored 24 rows.
- Sort works. Choosing Metric id reordered the table to M314650, M324043, M325402, and so on, and set `sort=metricId:asc`.
- Org multi-select cascades. Super_Division_01 narrowed Division to Division_01_01, Division_01_02, and Division_01_03, and the count went from 24 to 20 (`l1=Super_Division_01`).
- “Has non-compliant rows” is a real checkbox. Turning it on set `hasNonCompliant=true`.
- Pagination is real once page size is 10: “Previous 1 / 3 · 24 Next”, then with the org filter “1 / 2 · 20”. Previous is disabled on page 1. Page 2 shows M337379 through M385945 and `page=2`.
- Clicking a metric cell opens a preview. The URL becomes `preview=M340202`. There is no invented application id on that path.
- The three agreed actions are present, labeled, and pointed at the right places:
  - **Open Summary / Details** → `/register/M340202`
  - **Open Investigation** → `/investigate/metrics/M340202`
  - **Chat with Agent** → a context-review dialog
- Chat with Agent shows both agents, neither selected (`aria-checked="false"` on both radios). Send stays disabled until one is chosen. Escape closes that dialog. No agent run was submitted.
- The metric investigation says “An application is opened only when you choose one” and “This page does not pick one for you.” It listed 15 applications. Choosing Application_00694 opened that application.
- On a successful application load the page names Application_00694 and EON743680, with Non-compliant, Failed test, and Persistent non-compliant chips, and counts of 1 metric, 1 non-compliant row, and 10 open findings.
- At 1440 the register page itself does not scroll horizontally. All seven columns fit (Trend ends at x=1392). The detail and investigation pages also had no page-level horizontal overflow at 1440 or at 390.
- Buttons in the preview are styled (primary blue, secondary outline, gradient Chat pill), not raw browser buttons. Warning callouts use an amber panel and a Retry button.

## Must fix

### 1. The concise preview is not something a person can find

- **Screen/component:** Metric register, row preview
- **Observation:** The page says “Preview opens on the right,” but there is no Preview control on the row, in the toolbar, or anywhere else in the document. The row is a plain `<tr>` with `cursor: pointer`, `tabindex="-1"`, no role, and no accessible name. The only keyboard target inside the row is the Provisional link, which goes to `/definitions#PD-01`, not the preview. Clicking the row does open a panel (`?preview=M340202`, `aria-label="Context preview"`). That panel is a long stats sheet: family, rate, applications, denominator, four count rows, the rate formula, and PD-01, PD-02, and PD-13 notes. It is 380px wide and about 719px tall, `position: sticky`, and it does not scroll inside itself (`overflow: visible` on the drawer and the body). The three actions sit in `.drawer-foot` under that essay.
- **Severity:** High
- **Category:** Interaction
- **Evidence:** At 1440×900, before any scroll, the drawer started at y=484 and the actions were at y=1059, y=1106, and y=1153, all below the 900px viewport. Close was visible at the top of the drawer; the actions were not. Focus stayed on `body`. Escape closed the chat dialog and left the drawer open. At about 390px the same drawer is not on the right. It is appended after the filters and all 24 rows (drawer y≈3116 on open). The click does not scroll it into view. Once scrolled to, the three labels are full width and readable (Open Summary / Details at y=674, Open Investigation at y=721, Chat with Agent at y=767 in a ~390px-wide card).
- **Impact:** A person looking for a concise preview, or using the keyboard, will not find one. Mouse users who click a row see a statistics sheet and still have to scroll before they can open the summary, the investigation, or chat. On a phone they see no change on the current screen.
- **Recommendation:** Add a visible Preview control on each row, and make the row itself a button or link with a name such as “Preview M340202”. Open a short right-hand drawer (full-width sheet on a phone) that shows the metric, the rate, and the three actions in the first view. Move focus into the drawer and return it on close. Close on Escape. Scroll the opened preview into view on a phone instead of leaving it below the table.
- **Scope:** Behavior and component (register row, `.drawer`). CSS for height, overflow, and the phone stack.

### 2. Register filters are native list boxes and bury the table

- **Screen/component:** Metric register toolbar, and the same lists on the metric detail page
- **Observation:** Month, Sort, M&A, and Page size are native `<select>` elements (`appearance: auto`). Super division, Division, Legal entity, Tier, Risk, Lifecycle, and Denominator are native multi-selects with `size` around 4–5, so each one is a 94–133px tall scrolling list. They are not menus, chips, or a filter popover. On the detail page the same lists stack in one column from about y=319 to y=1160, and the rate chart does not start until y=1216. The investigation page is better: those lists stay behind a Filters button.
- **Severity:** High
- **Category:** Visual
- **Evidence:** At 1440 the first toolbar is a wrapping flex row, 1129×219. Lifecycle’s list ends at x=1313. Tier’s list is 49px wide. At 390 the lists fill the first screen. Option text is cut inside the controls (Super_Division_01, Legal_Entity_07, Division_01_01). The screenshot at the bottom of that screen shows Lifecycle fully, then M&A and Clear squeezed beside it, and the metric table still below the fold. The detail page at 1440 places an 800px-tall stack of these lists before “Rate over time” and “Contributing applications.”
- **Impact:** The register looks like an unstyled admin form. The lists consume the first viewport, which is why the preview actions and, on a phone, the table itself start off screen. Option labels are clipped, so a person cannot read the value they are about to select.
- **Recommendation:** Use the investigation page’s Filters button on the register and the detail page. Inside it, use a single-line multi-select (chips or a menu), not a always-open `size="5"` list. Keep Month, Search, and Sort on one compact row.
- **Scope:** Component / CSS for the register and detail toolbars. The filter behavior (URL params, cascading Division) can stay.

### 3. On a phone the register table clips the rate badge and hides three columns

- **Screen/component:** Metric register table at ~390px
- **Observation:** The page itself does not scroll sideways (`scrollWidth` 390). The table does. `.table-wrap` is about 358px wide and the table is 754px wide, so RATE, NON-COMPLIANT, DENOMINATOR, and TREND start at x=300, 401, 530, and 647. The visible RATE cell shows “44.5” and then cuts the Provisional chip to “Provisio”. FAMILY wraps “Not available” onto two lines and puts a second “Not available” chip under it, so the row is 97px tall. With the preview open the drawer’s right edge is 396 against a 390 client width, a few pixels of page overflow.
- **Severity:** High
- **Category:** Responsive
- **Evidence:** Phone screenshot of the table footer area after scrolling past the filters, plus the column boxes above. At 1440 with the drawer closed, the same seven columns fit. With the drawer open at 1440 the table’s scroll width is 754 against a 727 client width, so a thin horizontal scrollbar appears under the grid.
- **Impact:** The compliance signal on each row, the Provisional chip, is cut off on a phone. The non-compliant count, denominator, and trend are off screen with only a thin scrollbar as a hint. Opening the preview makes the desktop grid scroll sideways as well.
- **Recommendation:** On a narrow width, drop to Metric, Rate, and a single status, or show the row as a card. Do not clip a chip at the scrollport edge. When the preview is open at desktop width, let the table shrink its columns instead of overflowing by ~30px.
- **Scope:** CSS (`.table-wrap`, register table, `.split`).

### 4. Chat with Agent does not move focus into the dialog

- **Screen/component:** Context review dialog opened from the preview
- **Observation:** The dialog is a real modal (`role="dialog"`, `aria-modal="true"`, `aria-label="Chat with Agent"`, fixed backdrop). Both choices are radios and neither is selected: “Analysis & Investigation” and “Data Explorer”. Send is disabled. Focus stayed on the Chat with Agent button behind the backdrop (`focusInDialog` was false). Escape does close it and returns focus to that button, because focus never left. The dialog is `width: min(520px, 100%)` and `height: 100%`, pinned to the right. Its scroll height was 1056 against a 900px client height, so Send (y=1003) is just below the first view. The agent cards themselves were on screen (y=704, height 176).
- **Severity:** High
- **Category:** Accessibility
- **Evidence:** Clicked Chat with Agent on the M340202 preview at 1440. Inspected `aria-checked`, disabled state, focus, and dialog geometry. Did not press Send.
- **Impact:** Keyboard and screen-reader users stay in the page underneath a modal. They can tab the register while the review is open. The agent choice is easy to miss under a long context dump, and Send is one short scroll further down.
- **Recommendation:** On open, move focus to the dialog heading or the first agent card, trap Tab inside the dialog, and restore focus to the invoking button on close. Put the two agent cards above the context checklist, or keep the checklist collapsed, so the choice and Send are in the first view.
- **Scope:** Behavior (focus) and layout of the chat dialog.

### 5. Shell wordmark still collides on these pages

- **Screen/component:** Sidebar brand, every screen in this audit
- **Observation:** At 1440, `.brand-name` is an inline box 56×39 at y=20 and `.brand-sub` is inline 114×35 at y=43. The boxes overlap, and the lockup reads as Metrics / AnalyzerApplication. At 390 the sidebar is a full-width bar (390×309) and the same spans still overlap (name bottom 40, subtitle top 24). The phone crop reads **Metrics AnalyzerApplication compliance intelligence** with no space.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Bounding boxes at both widths, and the phone and desktop screenshots of the register, detail, and application investigation.
- **Impact:** The product name is hard to read on every metric screen.
- **Recommendation:** Make the name and the subtitle separate blocks, with the subtitle starting below the name. On the phone bar, keep them on one line only with an explicit gap.
- **Scope:** CSS (`.brand-name`, `.brand-sub`). Same shell defect as the dashboard audit; it is still on these routes.

## Optional polish

### 6. Phone chrome spends the first screen on navigation and the status line wraps

- **Screen/component:** Sidebar and status line at 390px
- **Observation:** The sidebar becomes a sticky full-width block 309px tall, including Utility, Definitions, Policy Control Office, and Earlier release, before “Metrics” starts. The status line wraps so “Data available” sits on its own line under the seed string.
- **Severity:** Medium
- **Category:** Responsive
- **Evidence:** Phone screenshots of the register, detail, and application investigation. Sidebar box was x=0, y=0, 390×309.
- **Impact:** A person has to scroll past navigation and a footer before the metric they came to see. The status line looks broken rather than like a quiet meta row.
- **Recommendation:** Collapse the phone nav to a single row plus a menu. Keep the status on one line, or hide the seed string on a narrow width.
- **Scope:** CSS for `.sidebar` under the narrow layout.

### 7. Context review repeats a heading as its own description

- **Screen/component:** Chat with Agent, context checklist
- **Observation:** One checklist row is a checkbox whose title and fine print are the same string: “Non-compliant applications (sample)”. The definitions chip in the summary reads `pd-1` rather than PD-01. The rest of the review is specific and useful: metric M340202, Oct 2026, 174 applications, numerator 69, denominator 155, provisional rate 0.445161, and the entry surface “Register preview”.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Dialog text and the row markup `<span class="t-title">` plus `<span class="fine">` with the same words. Both agent radios unchecked.
- **Impact:** That checklist row does not tell anyone what will be sent. The lowercase id looks like a raw key.
- **Recommendation:** Give the sample row a description of what the sample contains. Show definition ids as PD-01.
- **Scope:** Component copy for the context checklist.

### 8. “Not available” is said twice in every family cell

- **Screen/component:** Register FAMILY column, and the same pair in the preview
- **Observation:** Each family cell is the text “Not available” plus a chip that also says “Not available”. On a phone the text wraps and the chip sits underneath, which is why rows are almost 100px tall. This matches the data (family is null; PD-13 says the UI shows not available). The repetition is presentation.
- **Severity:** Low
- **Category:** Visual
- **Evidence:** Row HTML and the phone table screenshot. Detail copy for PD-13 explains the null family.
- **Impact:** The column looks like a placeholder, and it steals vertical space from the preview on a phone.
- **Recommendation:** Show one chip, “Not available”, and drop the duplicate text.
- **Scope:** Register cell component.

### 9. Clickable rows have no hover fill

- **Screen/component:** Register table rows
- **Observation:** Rows use `cursor: pointer`. The only row background rule found is `tr.sel` after the preview is open. There is no `tr:hover` fill. The selected row does pick up the accent tint once the preview is open.
- **Severity:** Low
- **Category:** Interaction
- **Evidence:** Stylesheet rules for `tr` and the highlighted M340202 row after click.
- **Impact:** Nothing in the row suggests it can be clicked, which compounds finding 1.
- **Recommendation:** Add a hover background, and keep the selected tint while the preview is open.
- **Scope:** CSS (`.table-wrap tr`).

## Not a styling bug

- The first desktop load of `/investigate/applications/EON743680?metric=M340202` showed a styled warning, “This response has no packaged extract for the current request,” with Retry, and no application heading. A later load of the same URL rendered Application_00694, the status chips, and history, including “Nov 2025 Not observed.” That is an intermittent packaged-extract failure, and the empty state is already designed (amber `.callout.warn`).
- On one phone load of `/register/M340202`, several cards said “Snowflake did not answer” or the same packaged-extract warning, each with Retry. The first warning sits in a 174px box beside the Month select (callout right edge 203, select at x=213). The failure is the service response. The cramped pairing with Month is a layout side effect, not the cause.
- A rate shown as “-” (M331979 in the filtered list) is an empty rate, consistent with a zero or null denominator, not a clipped glyph.
- Family “Not available” is the documented PD-13 state when the source family is absent. Only the duplicate label is a presentation issue.

## Critical and High

No Critical defects. The preview path exists, and the three actions go to the right places.

High:

1. No Preview control and no keyboard path. Row click opens a long stats drawer. The three actions are below the first screen at 1440, and below the whole table on a phone.
2. Register and detail filters are always-open native multi-selects. They clip their labels and push the table and the preview off the first screen.
3. At 390px the register table cuts off the Provisional chip and hides Non-compliant, Denominator, and Trend inside a horizontal scroll.
4. The Chat with Agent modal does not take focus, so the review opens over a page that still has focus.
5. The shell wordmark still collides on every screen in this pass, including the phone bar.
