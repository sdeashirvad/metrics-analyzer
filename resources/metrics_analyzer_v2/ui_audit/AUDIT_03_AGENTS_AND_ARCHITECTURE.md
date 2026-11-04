# Audit 03 — Agents and architecture

Live app only. Desktop layout viewport 1440×900. Phone layout viewport 390×844 (`Emulation.setDeviceMetricsOverride`, cleared afterward). No source, config, or server changes. No second agent run was started: an existing Analysis & Investigation thread was already in Recent.

Screens exercised: `/agent`, `/agent/analysis`, `/agent/data`, the saved analysis thread, `/architecture` (walkthrough advanced to step 1 of 9), `/definitions`. Navigation on these pages has Dashboard, Metric register, Agent, Architecture, and Definitions & conventions. There is no Triage item. Architecture is the new app at `/architecture` (POC Design and Proposed Design), with Earlier release as a separate link.

The IDE screenshot pane is narrower than the 1440 layout, so right-edge cropping in captures was checked against layout geometry. A control is reported as clipped only when it overflows its box or the 1440/390 layout viewport.

## Critical and High

No Critical findings.

1. **High — Shell wordmark.** “Metrics Analyzer” and “Application compliance intelligence” run together as “Metrics AnalyzerApplication” on desktop and phone.
2. **High — Agent setup composer.** The message field has no border, background, placeholder, or focus ring. Send sits under a blank gap.
3. **High — Analysis answer.** The completed narrative shows raw Markdown (`**923…**`) and collapsed line breaks.
4. **High — Architecture dock (desktop).** The sticky walkthrough bar covers the selected node’s detail, including the Inputs line.
5. **High — Architecture on a phone.** After scroll, diagram nodes paint over the sticky navigation and take the click from Dashboard.

## Must fix

### 1. Wordmark collides with the subtitle

- **Screen/component:** Shell wordmark (`.brand-name` + `.brand-sub`), every page in this pass
- **Observation:** The product name and the subtitle are adjacent inline spans with no break. On a 1440px desktop, “Metrics” wraps onto its own line and “Analyzer” shares the next line with “Application”. The name and subtitle boxes overlap by about 16px vertically. On a 390px phone they sit on one line and touch: “Metrics AnalyzerApplication compliance intelligence”.
- **Severity:** High
- **Category:** Visual
- **Evidence:** Desktop 1440×900, `/agent`. Name line boxes at y=20 (“Metrics”) and y=40 (“Analyzer”, right edge 105). Subtitle “Application” starts at x=105, y=43. Phone 390×844, same pages: name ends at x=157, subtitle starts at x=157. Seen on agent landing, both agent setup screens, the thread, architecture, and definitions.
- **Impact:** The product name is unreadable in the shell. It is the first thing on every screen.
- **Recommendation:** Stack the name and subtitle as two blocks (name on one line, subtitle below, full width of the brand slot). Do not leave them as sibling inline spans.
- **Scope:** Component / CSS (`.brand`)

### 2. Message field on agent setup is invisible

- **Screen/component:** Agent setup composer, Analysis & Investigation and Data Explorer (`/agent/analysis`, `/agent/data`)
- **Observation:** The textarea is 72px tall and full width, with a transparent background, no border, an empty placeholder, and `outline: none` while focused. The only cues are the “MESSAGE” label and a full-width Send pill. Focusing the field changes nothing on screen. Send stays disabled until there is text, so the blank gap does not look like an input.
- **Severity:** High
- **Category:** Visual, Interaction, Accessibility
- **Evidence:** Desktop 1440×900. Clicked the message textbox on `/agent/analysis`; accessibility state became focused and `document.activeElement` was the textarea, with `outline-style: none`, `box-shadow: none`, `border: 0`, `background: transparent`. The same unmarked gap is on `/agent/data` between MESSAGE and Send.
- **Impact:** A person cannot see where to type or whether the field has focus. The primary action of both agents is easy to miss.
- **Recommendation:** Give the field a visible well (border, fill, radius, min height) and a placeholder such as “Ask about the portfolio”. Show a 2px focus ring on the field. Keep Send disabled until there is text, and keep it a compact button at the end of the field rather than a bar the width of the page.
- **Scope:** Component / CSS (`.field`, `textarea`, `button.ask`)

### 3. Completed analysis answer shows raw Markdown

- **Screen/component:** Analysis conversation narrative
- **Observation:** The agent’s answer is inserted as plain text inside a paragraph. Bold markers stay visible, and newline breaks collapse because the paragraph’s white-space is `normal`.
- **Severity:** High
- **Category:** Functional
- **Evidence:** Desktop 1440×900. Opened Recent “How many applications reported?”. The bubble text begins `**923 applications reported for the month ending 2026-10-31**`. The element is a single `<p>` whose HTML contains the asterisks and a blank line; computed `white-space` is `normal`. The hypothesis line above it (“Agent-generated. Explanations of cause are hypotheses until validated.”) does render as intended.
- **Impact:** The main answer looks unfinished. Emphasis and paragraph structure from the agent are lost. This is a presentation defect, not a Snowflake delay: the run is already complete and the SQL result is on the page.
- **Recommendation:** Render a safe subset of Markdown (bold, paragraphs, lists) into the answer bubble. Keep the hypothesis notice as real text above it.
- **Scope:** Component / behavior (answer renderer)

### 4. Walkthrough bar covers the architecture detail

- **Screen/component:** `/architecture` walkthrough dock (`.arch-dock`) over `.arch-detail`
- **Observation:** The dock is `position: sticky` at the bottom of the 900px viewport and sits on top of the selected node’s detail. Advancing the walkthrough works, and the covered text moves with the step.
- **Severity:** High
- **Category:** Visual, Interaction
- **Evidence:** Desktop 1440×900, `/architecture`. Dock rect y=816, height 68, z-index 5. Detail section y=676, height 313, so they overlap from y=816 to y=884. Clicked Next. The dock changed from “9 steps” to “Step 1 of 9 — Open an investigation”, and the pressed node changed to Risk stakeholder. The Inputs line “Dashboard, register, investigation, and agent links” is crossed by the dock.
- **Impact:** The step explanation and the node detail fight for the same space. The text the walkthrough is meant to explain is partly unreadable.
- **Recommendation:** Pin the dock below the detail, or add bottom padding on `.arch-detail` equal to the dock height so the detail never slides underneath it. Keep the dock sticky only if the content above it can scroll clear.
- **Scope:** CSS (`.arch-dock`, `.arch-detail`)

### 5. On a phone, the architecture diagram covers the navigation

- **Screen/component:** Sticky sidebar and architecture nodes at 390px
- **Observation:** The sidebar stays pinned to the top (`position: sticky`, about 309px tall, z-index auto, 72% white). After scrolling the architecture page, diagram nodes and the “Experience” heading occupy that same band and receive the hit test instead of the nav links. Page-level horizontal overflow is 0. Other pages checked at this width (definitions, the analysis thread) still hit the Dashboard link.
- **Severity:** High
- **Category:** Responsive, Interaction
- **Evidence:** Phone 390×844, `/architecture`, scrolled 520px. Risk stakeholder at y=84 and React + Vite UI at y=150 overlap the sidebar (bottom 309). `elementFromPoint` on the Dashboard link returned the “Experience” heading, not the link. Screenshot shows the node boxes drawn across Dashboard, Metric register, and Definitions & conventions.
- **Impact:** Primary navigation cannot be used while the diagram is scrolled up. Links look present but the click lands on the diagram.
- **Recommendation:** Give the sticky sidebar a solid background and a z-index above page content. On this breakpoint, collapse the nav behind a menu so the diagram can use the width without sliding underneath it.
- **Scope:** CSS (`.sidebar`, architecture stacking)

## Optional polish

### 6. “Available” status stretches into a full-width bar

- **Screen/component:** Agent choice cards on `/agent`
- **Observation:** Both cards use a flex column, so the “available” chip stretches to the text column. It is a 999px-radius pill with a grey fill, so it reads as a bar, not a status chip. The two cards are otherwise distinct: blue top border for Analysis & Investigation, teal for Data Explorer, and the descriptions differ.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Desktop 1440×900: each `.agent-card .chip` is `display: flex` and 522px wide. Phone 390×844: each chip is 316px wide inside a 358px card. Nothing is preselected; both cards are links (`/agent/analysis`, `/agent/data`).
- **Impact:** The landing looks unfinished. The status is harder to scan than a small chip.
- **Recommendation:** `align-self: flex-start` on the chip, and keep the teal versus blue top borders.
- **Scope:** CSS (`.agent-card`, `.chip`)

### 7. Data Explorer loses its color once selected

- **Screen/component:** Selected agent card on `/agent/data` and `/agent/analysis`
- **Observation:** On the landing page the Data Explorer card has a teal top border (`rgb(15, 111, 115)`) and Analysis has blue (`rgb(35, 87, 197)`). On the setup screen, `.agent-card.data.is-selected` uses the same blue top border and the same blue selection ring as Analysis. Copy and the switch link still differ. The setup eyebrow on both screens is “AGENT”.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Desktop 1440×900. Landing computed borders as above. `/agent/data` selected card computed `border-top-color: rgb(35, 87, 197)` and a blue 3px ring. Switch link reads “Switch to Analysis & Investigation”. The analysis thread eyebrow reads “ANALYSIS & INVESTIGATION”.
- **Impact:** After the choice, the two agents look like one blue form with a different title. They still share one product shell, which is right; the accent that told them apart is gone.
- **Recommendation:** Keep the teal top border and a teal ring on the Data Explorer card and thread. Use “DATA EXPLORER” as the eyebrow on that agent’s screens.
- **Scope:** CSS / component (`.agent-card.data.is-selected`)

### 8. Context checklist uses native checkboxes, and one row repeats its title

- **Screen/component:** “Review the context” include list, both agents
- **Observation:** The include rows are native checkboxes (`appearance: auto`, 13×13). Required rows are disabled and checked. Optional rows can be toggled. The Portfolio trend description is the same string as the title, so the row reads “Portfolio trend Portfolio trend”. The other rows have real descriptions (“Applications reporting: 923.”).
- **Severity:** Medium
- **Category:** Visual, Accessibility
- **Evidence:** Desktop 1440×900, `/agent/analysis`. Six inputs, `appearance: auto`, 13×13. Portfolio trend markup is `<span class="t-title">Portfolio trend</span><span class="fine"> Portfolio trend</span>`. The label row is the click target, so the 13px box is not the only hit area.
- **Impact:** The checklist looks like default browser controls next to custom type. The repeated title looks like a missing description.
- **Recommendation:** Use the same custom checkbox as the rest of the product, at least 24px on touch. Give Portfolio trend a real one-line description, or show the title only.
- **Scope:** Component (context checklist)

### 9. “Exact text sent” does not wrap

- **Screen/component:** Exact-text disclosure on agent setup
- **Observation:** Opening the disclosure shows a dark monospace block with `white-space: pre`. Definition lines are single long lines. The block scrolls sideways inside itself. The page does not scroll sideways.
- **Severity:** Medium
- **Category:** Visual, Interaction
- **Evidence:** Desktop 1440×900, `/agent/analysis`. Opened “Exact text sent”. The `<pre>` client width is 1129px and scroll width is 2943px. Longest line is 398 characters (PD-10 organisation trees). Provisional wording is present in the text (“provisional”, “not client-confirmed”).
- **Impact:** The review step hides the rules the person is asked to accept, behind a horizontal scrollbar.
- **Recommendation:** Use `pre-wrap` for this prose. Keep a horizontal code scroller only for SQL.
- **Scope:** CSS (exact-text `<pre>`)

### 10. Definition status is visible, and also shown twice in raw form

- **Screen/component:** `/definitions` cards
- **Observation:** Provisional analytics are on the page and labelled, not hidden. Eleven items carry a gold “Provisional” tag. The same items also carry a grey chip whose text is the raw token `provisional`. Other classes are raw tokens: `assumption` (PD-02), `source` (PD-10 Organisation trees), `documented_rule` (PD-04, PD-05, PD-07, PD-11, PD-12), and `not_available` (PD-13 Source metric family, still shown). At 1440 the tags sit on the right of the title and do not overlap it. At 390 the title wraps and the tags sit beside it; “Non-compliant application” shows PD-03, gold Provisional, and grey `provisional`.
- **Severity:** Medium
- **Category:** Visual
- **Evidence:** Desktop 1440×900 and phone 390×844, `/definitions`, after the loading line cleared. Badge counts: Provisional 11, provisional 11, documented_rule 5, assumption 1, source 1, not_available 1. No horizontal page overflow at either width.
- **Impact:** Provisional work is honestly labelled. The duplicate token and snake_case values look like an API dump rather than a legend a stakeholder can scan.
- **Recommendation:** Show one human label per card: Provisional, Assumption, Source observation, Documented rule, Not available. Drop the second `provisional` chip. Add a one-line legend at the top of the page.
- **Scope:** Component (definition card badges)

### 11. Phone shell is a full navigation block, and SQL scrolls inside the code block

- **Screen/component:** Sidebar at 390px; SQL `<pre>` on the analysis thread
- **Observation:** At 390px the sidebar becomes a full-width block about 309–380px tall. Links wrap onto two columns and stay on screen. There is no horizontal page overflow on the landing, thread, architecture, or definitions. The SQL block does scroll inside itself (scroll width 519 vs client width 282), so long tokens are cut until that inner scroll. The result table fits: APPS_REPORTING 923 and APPS_IN_DATASET 1500, headers not clipped. Follow-up questions wrap onto two lines and stay inside the card. The walkthrough dock’s computed position at this width is `static`, so Next / Play sit at the end of the stacked diagram rather than on the screen.
- **Severity:** Medium
- **Category:** Responsive
- **Evidence:** Phone 390×844. Landing cards stack at x=16, width 358, right edge 374, with full descriptions. Thread table cells are not clipped. Architecture nodes stack at width 358 with no page overflow. Dock `position: static`, `bottom: 16px` not applied as sticky.
- **Impact:** The first phone screen is mostly navigation. SQL is readable only after an inner horizontal scroll. The guided controls are easy to miss until the bottom of a long diagram.
- **Recommendation:** Collapse the phone nav into a menu. Keep SQL in an obviously scrollable code well. Pin the walkthrough controls to the bottom of the phone viewport without covering the node text.
- **Scope:** CSS / behavior (sidebar breakpoint, `.arch-dock`, SQL `pre`)

### 12. Small copy and feedback gaps

- **Screen/component:** Query meta line; Copy SQL; thread composer
- **Observation:** The success line says “1 rows”. Copy SQL keeps that label after a click: no “Copied” state and no error. The thread composer is a real bordered card (better than setup) and still has no placeholder. Tool names `ApplicationComplianceAnalyst` and `system_execute_sql` are shown as the evidence trail, with RESULT on the right.
- **Severity:** Low
- **Category:** Interaction, Visual
- **Evidence:** Desktop thread. Meta text: “Query 1 · system_execute_sql · success · 1 rows”. After clicking Copy SQL the button text stayed “Copy SQL”. Follow-up composer form has a 1px border and 16px radius; the textarea inside has no placeholder.
- **Impact:** Small rough edges on an otherwise readable result. Copy may have succeeded silently; there is no visible success or failure.
- **Recommendation:** Use “1 row” / “N rows”. After copy, set the button to “Copied” for a moment, or show an inline error if the clipboard is blocked. Add a follow-up placeholder. Present the tool trace as “Query” rather than the internal tool id, and keep the SQL itself.
- **Scope:** Component / behavior

## What already works

- Agent landing does not preselect an agent. The intro says nothing is chosen until you pick one. Analysis & Investigation and Data Explorer are separate links with different descriptions: evidence-backed explanation versus read-only SQL and the returned dataset.
- Each setup screen names the chosen agent and offers a switch to the other. Recent holds the analysis thread only; opening it does not mix in a Data Explorer history.
- The saved analysis thread shows a completed, successful state: hypothesis notice, narrative, SQL, “Copy SQL”, a two-column table (923 and 1500), “1 rows”, Export, and three follow-up questions. That is a finished result, not a stuck running state. No failed or in-progress run was on screen.
- Provisional language is visible in the answer (“that coverage figure is provisional”), in the exact-text payload, and on `/definitions`. Source, assumption, documented rule, and not-available items are listed rather than hidden.
- `/architecture` is the new diagram, with POC Design selected, Proposed Design available, and a walkthrough that advances (step 1 of 9 highlights Risk stakeholder and React + Vite UI). Node labels are not clipped inside their boxes at 1440. The diagram fits the 1440 content column (rightmost node at x=1388, no page overflow).
- At 390px the agent cards, result table, follow-ups, and definition cards fit without page-level horizontal overflow. Definitions still show the gold Provisional tag.
- Shell status is an honest ready state: Snowflake, seed v1-seed20261103, Oct 2026, Analysis available, Data available. Skip to content is present. No Triage item.

## Not treated as defects

- Screenshot crops past about 760px were the capture pane, not layout overflow. At 1440 the second agent card, the subtitle, the SQL, and the definition badges fit in the layout viewport.
- No new agent run was sent, so a live “running” state was not observed. The completed thread is the state that was actually on screen.
- Contextual agent entry (a metric already selected) is not offered on these agent pages. Metric is None and the entry surface is General. Reaching a metric-scoped agent would go through the register, which this pass did not re-audit.
