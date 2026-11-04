# Live demo gap test plan

Status: not run. Written 4 Nov 2026 after the revamped-v1 deploy, for a later pass.

The core demo path was already exercised live and is out of scope here: dashboard, register, Preview for M340202, Summary, Investigation AI for M340202, Definitions, Architecture, and one Analysis agent message. This plan covers the four gaps left from that pass.

## Environment

- Frontend: https://metrics-analyzer-poc.pages.dev/
- API: https://metrics-analyzer-backend.sdeashirvad.com/api/v1
- Image on the VM: `sdeashirvad/metrics-analyzer-backend:revamped-v1` (digest `sha256:6d8bd019d609e9d70a42a66f79d603f0fefb26acec6beb72ebf40041700a4a5e`)
- VM: `ubuntu@140.245.220.83`, compose and env in `/opt/metrics-analyzer/`. Backups from the deploy are `docker-compose.yml.bak-20261104T165611Z` and `.env.bak-20261104T165611Z`.
- Do the outage case in its own window. Restore the env file before any demo.

Record for each case: pass or fail, URL, time, and a screenshot or response snippet when it fails.

## 1. Data Explorer agent

Open https://metrics-analyzer-poc.pages.dev/agent in a fresh browser profile so history starts empty.

1. Select **Data Explorer** (not Analysis & Investigation). Confirm the composer enables and the placeholder changes.
2. Send: `How many applications reported in October 2026, and how many of them were non-compliant? Keep it to the numbers.`
3. Wait until the reply finishes. Expect a dataset-style answer: a short statement, a SQL block, and a result table. The figures should match the dashboard: 923 reporting, 300 non-compliant.
4. Confirm the history rail shows the new conversation under Data, and reloading the page still shows it.
5. Start a new conversation, select **Analysis & Investigation**, and confirm the Data Explorer thread stays on Data and cannot be switched mid-thread.
6. Send one follow-up in the Data Explorer thread (`Break that down by super division.`) and confirm it stays on the same conversation.

Pass: both replies complete without "Stop waiting" being required, the result table renders, history survives a reload, and the agent stays fixed per conversation.

Watch for: a reply that hangs past about 90 seconds (Cloudflare cuts proxied requests near 100 seconds), an empty table, or the UI labelling the reply as Analysis.

## 2. Snowflake outage fallback on the VM

Local outage was already proven with `SNOWFLAKE_ACCOUNT=outage-simulation-unreachable.invalid` and `backend/scripts/outage_walk.py`. This case repeats that on the running VM. It takes the live API off Snowflake for a few minutes.

1. SSH in and copy `/opt/metrics-analyzer/.env` to a fresh backup (`sudo cp -p .env .env.bak-outage`).
2. Change only `SNOWFLAKE_ACCOUNT` to `outage-simulation-unreachable.invalid`. Leave the password and every other key as they are.
3. `sudo docker compose up -d` in `/opt/metrics-analyzer` and wait until `metrics-analyzer-api-1` is healthy.
4. From outside the VM, check:
   - `GET /api/v1/portfolio/status` returns 200 and `source` is the offline pack, not `snowflake`.
   - `GET /api/v1/portfolio/metrics` returns 200 with the same 24 metrics.
   - `GET /api/v1/portfolio/investigations/metrics/M340202` returns the prepared analysis.
   - `GET /api/v1/agents` still lists both agents.
5. Open the live dashboard, register, and `/investigate/metrics/M340202`. Pages should render from the pack, with the freshness label showing offline or packaged data rather than "Live data".
6. Send one Agent message. Expect a clear unavailable or offline message, not a hung composer. The "Stop waiting" control should remain usable.
7. Restore: `sudo cp -p .env.bak-outage .env`, then `sudo docker compose up -d`. Confirm `/portfolio/status` is `source: snowflake` again and the dashboard says "Live data".

Pass: portfolio pages keep working from the pack, the agent fails closed with a readable message, and Snowflake is the source again after restore.

Stop the case if the container does not return to healthy within two minutes of restore, and roll the compose image tag back to `v2` using the deploy backup.

## 3. The other 23 prepared investigations

M340202 was opened live on 4 Nov 2026 and showed the AI Investigation section. Open each remaining metric at `https://metrics-analyzer-poc.pages.dev/investigate/metrics/<id>` with month Latest (2026-10-31).

M314650, M324043, M325402, M325951, M327707, M328162, M328814, M331979, M333387, M333622, M334559, M337379, M343112, M343367, M344745, M346318, M366104, M366446, M369375, M384010, M384271, M385554, M385945.

For each id, check:

- The page heading is that metric id and the rate card has a number and a band.
- The AI Investigation block is present, labelled prepared or agent-generated, and contains an executive finding for that same metric id and month 2026-10-31.
- The block is not the M340202 text and not an empty or error state.
- "Back · Register" returns to the register, and Preview from the register opens the same metric.

A shorter pass is acceptable if time is short: open five ids that differ in band (one Healthy, one Watch, one Needs attention) plus M343367, whose prepared note calls out a rate-direction caveat. The full list is the pass bar for "every prepared analysis is reachable".

Pass: all 23 render their own prepared note. Any id that shows another metric's text, a spinner that never ends, or a missing AI section is a fail.

## 4. Other devices and viewports

Use the same live URL. Cover one phone-width browser (390px wide, or a real phone), one laptop at 1440px, and one wide display at 1920px standing in for a projector. Chrome is the browser already used; repeat the phone-width pass in Edge or Firefox if a second browser is available.

On each viewport walk: Dashboard, Register (open one Preview, then close it), `/investigate/metrics/M340202`, Agent landing, Definitions, Architecture.

Check:

- No horizontal page scroll on the shell. Tables may scroll inside their own region.
- The sidebar collapses or stays usable, and "Skip to content" is not the only way to reach the page.
- Preview modal fits the viewport, its close control is visible, and Escape or the close button dismisses it.
- The Agent composer and Send button stay on screen without covering the reply.
- Text in the AI Investigation section wraps and does not overflow the card.
- On the wide display, cards do not stretch into a single unreadable line; the dashboard grid still reads as separate cards.

Pass: each viewport completes the walk with the same data as desktop and no clipped primary action.

## Order

Run 1, then 3, then 4 while Snowflake is up. Run 2 last, and only after the restore check, so a failed restore is the last thing you notice rather than the thing that blocks the other cases.
