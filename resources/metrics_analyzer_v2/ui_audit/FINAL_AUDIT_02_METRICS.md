# Register, preview, and investigation — 4 November 2026

Live app: http://127.0.0.1:5173. API: http://127.0.0.1:8080.

## Preview

Opened Preview on the register. The dialog was 500px wide, top at 72px, left at 819px. The content-area centre was 1076px and the dialog centre was 1069px. The register table stayed 1294px wide, so the table did not reflow.

The subtitle now says the preview opens over the table.

## Prepared analysis

GET `/api/v1/portfolio/investigations/metrics/M340202` returned status `FALLBACK_STATIC` with the Analysis agent’s own text, beginning “The data can't tell us what the provisional green band is.”

On the page the panel heading was “Prepared analysis”. The internal status was not shown. A follow-up field was present. A limitation note was visible because source-fact validation is PARTIAL: the supplied figures were checked, and other numbers in the prose were not all tied to a source query.

GET `/api/v1/portfolio/investigations/metrics/M328814` returned `NOT_RUN`. That metric is outside the six prepared bundles, so the panel stays on “No analysis yet” until Explain with AI is used.

## Result

The centred preview and the prepared-analysis panel behave as specified. Summary and Investigation were not collapsed back into each other in this pass.
