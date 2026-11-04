# Post-refinement audit

Checked on 4 November 2026 against http://127.0.0.1:5173 and http://127.0.0.1:8080 after the RAG, Path to Green, and Agent pass. This is the implementation owner's consolidation. Findings name the screen, the action, and the result.

## 1. Dashboard and shared system

At a 1440px layout viewport the six cards measured:

| Card | x | y | width | height |
| --- | ---: | ---: | ---: | ---: |
| Compliance mix | 264 | 325 | 557 | 325 |
| Movement and attention | 837 | 325 | 557 | 613 |
| Testing distribution | 264 | 938 | 557 | 427 |
| Non-compliant share | 837 | 938 | 557 | 294 |
| Where it concentrates | 264 | 1365 | 557 | 363 |
| Legal entities | 837 | 1365 | 557 | 348 |

Compliance mix and movement share a row. Testing sits under compliance. The trend sits under movement. No horizontal overflow (`scrollWidth` matched `clientWidth`).

The first attention row did not overlap: the name was 118px wide and the status chip started at x=987.

Compliance mix is labelled "Metric rows, not applications" (1,096 rows) and separately "Application count" (300 / 623 / 923). Org and legal bars still show count and percent.

The testing card was 133px taller than the trend card on that capture. A stretch rule (`.grid.pair`) was added afterwards so that row shares one height. It was not remeasured in this pass.

KPI links, compliance segments, attention links, and org bars were present and named in the accessibility tree. Clicks were not repeated in this pass because those handlers were unchanged.

## 2. Register, preview, summary, investigation

The definitions payload now includes the provisional note: green below 0.45, amber below 0.60, red at 0.60 and above, fraction not percent.

A warm register read returned 24 metrics: 4 green, 10 amber, 10 red. The earlier 20/40 proposal would have been 0 / 2 / 22.

The register page itself returned "This response has no packaged extract" on the first paint after the API process restarted. That is the existing 5-second read budget and 30-second fallback gate, not a missing RAG field. A direct call a moment later returned the 4 / 10 / 10 split. Sorting and paging by RAG are covered by `test_provisional_rate_formula` (boundary values 0.449999, 0.45, 0.599999, 0.60, and null; two red rows stay red across page size 1).

Preview CSS is content height, max 70vh, width up to 400px, fixed, lighter backdrop. It was not reopened in the browser during the Snowflake cooldown.

Summary no longer renders the application table. Investigation no longer renders the funnel, the second trend, or the grey flag paragraphs. Path to Green is on both investigation pages. Application green is Compliant + Test_Complete + Pass, and the unit test rejects Pending, Not_Applicable, and Fail.

## 3. Agent, rendering, loading, Architecture

`/agent` still opens the workspace. After an agent is chosen the large cards collapse to two small buttons. Send stays available to pointer and keyboard when no agent is selected, with the sentence "Choose an Agent above to enable sending." and `aria-disabled`. The draft is not cleared.

Context cards say "Provisional definitions for this scope" and "Context is taken from this scope" instead of `pd-1` and a character count.

A running thread says "Analysing your request…" or "Working on your request…". Stop waiting still says the server run continues. No live Cortex message was sent in this pass, so SQL rendering and the loading animation were not exercised against a new answer.

Parser tests: mixed prose plus `system_execute_sql` keeps the sentence and the SQL rows; a JSON tool payload and the word SECRET do not appear in the answer; `UNKNOWN_BLOCK_TYPE` is absent.

Architecture was not re-walked. It was not part of the code change.

## Checks

- Frontend: 13 files, 57 tests passed. `npm run build` passed.
- Backend: `tests/v2/portfolio/test_portfolio.py` and `tests/v2/agents/test_parse.py`, 17 passed.

## Still open

- Re-measure the testing and trend row after the stretch rule, once the portfolio reads are warm.
- Open Preview, Summary, Investigation, and `/agent` in the browser after the fallback gate clears. The register error seen here was the cold Snowflake read, and it should not be treated as a layout defect.
