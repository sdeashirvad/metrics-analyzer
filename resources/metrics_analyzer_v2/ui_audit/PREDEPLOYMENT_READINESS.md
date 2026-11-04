# Pre-deployment readiness — 4 November 2026

Local only. No commit.

## Exercised

- Dashboard columns at desktop: Testing sits directly under Compliance mix. Measured y 666 versus Movement still at y 325.
- Register preview: 500px, centred in the content area, table width unchanged at 1294px.
- Agent composer: one field, helper and Send on the bottom bar, no inner border.
- Prepared investigations: six JSON bundles under `backend/app/fallback_assets/v2/investigations/`. Generation report records PASS context reconciliation and PARTIAL source-fact validation. The page for M340202 shows “Prepared analysis” and the agent’s text. M328814 stays `NOT_RUN`.
- Frontend: 63 tests passed, production build passed.
- Backend: portfolio, parser, and bundle tests passed (24, then the bundle file again at 8).

## Limits

- Source-fact validation is PARTIAL on every published bundle. The rate, counts, and other figures that appear in the prose were not all tied back to a source query. The files say so. They do not claim the explanation was fully validated.
- A new Data Explorer run was not sent in this pass.
- Architecture was not re-walked.
- The three notes in this folder are screen checks from this verification, written after the UI changes. They are not a claim that three separate auditors ran at the same time.
