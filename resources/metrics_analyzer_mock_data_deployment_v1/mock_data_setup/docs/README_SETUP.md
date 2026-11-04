# Metrics Analyzer – Mock Data Setup (Snowflake)

**Target:** database `METRICS_ANALYZER` (already exists) → new schema `METRICS_ANALYZER.MOCK_DATA`.
**Never touched:** `METRICS_ANALYZER.DQ`. No script references it except the read-only preflight listing and a "do not touch" comment.
**Dataset:** 11399 rows × 57 columns, 1,500 applications, 24 metrics, 12 month-ends (2025-11-30 → 2026-10-31). Batch id `MOCK_V1_20261103`.

> **Honest status.** Every SQL statement in this package is **UNEXECUTED**. It was written from Snowflake documentation and checked for internal consistency (column lists generated from the real CSV header, expected values computed from the real CSV, golden SQL run in a local SQLite emulation). It has **not** been run against Snowflake. Treat the first run as a supervised dry run: stop at the first unexpected result and send me the output.

## 1. What is in the ZIP

`metrics_analyzer_mock_data_deployment_v1.zip` extracts to a folder `mock_data_setup` containing:

| Path | Purpose |
|---|---|
| `data/synthetic_enterprise_data.csv` | **The only file you load.** SHA-256 `08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3` |
| `data/synthetic_enterprise_data.xlsx`, `data_dictionary` (inside the xlsx), `validation_report.md`, `data_profile.json`, `assumptions_register.md` | Reference only. Never loaded. |
| `data/generate_client_dataset.py` | Generator (seed 20261103) for reproducibility. |
| `sql/00_preflight.sql` … `sql/15_smoke_tests.sql` | Run in order, one file at a time. |
| `sql/ALL_IN_ORDER.sql` | The same scripts concatenated (convenience only; run script by script the first time). |
| `agent/` | `agent_specification.yaml`, `agent_instructions.md`, `golden_questions.md` |
| `docs/` | This file, DATA_MODEL, SEMANTIC_MODEL, AGENT_CONFIGURATION, PERMISSIONS, ROLLBACK |
| `MANIFEST.txt` | File list with SHA-256 for every file |

## 2. Extract the ZIP on Windows (PowerShell)

Assuming the ZIP is in your Downloads folder:

```powershell
cd $HOME\Downloads
Expand-Archive -Path .\metrics_analyzer_mock_data_deployment_v1.zip -DestinationPath .\metrics_analyzer_mock_data_deployment_v1
cd .\metrics_analyzer_mock_data_deployment_v1\mock_data_setup
Get-ChildItem
Get-FileHash .\data\synthetic_enterprise_data.csv -Algorithm SHA256
```

The hash printed must equal `08df1af542daf11c496355680d21de5d01618bf9220c965cdc75ac74c0cfbca3`. If it does not, the file changed in transit: stop and re-download. (File Explorer's *Extract All…* works equally well.)
If Windows opened the CSV in Excel and you saved it, **discard that copy** – Excel rewrites dates and can change line endings. Use the extracted original.

## 3. What you need to decide before starting

| Placeholder | How to find it | Where it goes |
|---|---|---|
| `<SETUP_ROLE>` | Run `00_preflight.sql`; a role with OWNERSHIP (or USAGE + CREATE SCHEMA) on `METRICS_ANALYZER` | `SET SETUP_ROLE` at the top of every script |
| `<WAREHOUSE_NAME>` | `SHOW WAREHOUSES` in preflight; reuse the one your DQ work uses | `SET WH_NAME` at the top of every script, **and once inside the agent specification in script 13** |

Each script starts with the same four-line header (`SET SETUP_ROLE …`, `SET WH_NAME …`, `USE ROLE`, `USE WAREHOUSE`). Edit the two quoted values in that header of each script before running. Nothing else needs editing.

## 4. Run order, checkpoints and where to stop

Open each file in a Snowsight worksheet (Projects → Worksheets → + → SQL worksheet), paste, edit the header, **Run All** (the dropdown next to Run). Compare each result with the **Expected** comment. If anything differs: **stop, copy the result grid and the error text, do not run the next script.**

| # | Script | What it does | Expected at the checkpoint | If wrong, capture |
|---|---|---|---|---|
| 00 | `00_preflight.sql` | Read-only discovery | Your role, a warehouse name, `DQ` schema listed, Cortex role grants | Output of 0.1–0.10 |
| 01 | `01_create_schema.sql` | Creates `MOCK_DATA` only | `SHOW SCHEMAS` lists DQ and MOCK_DATA | Error text, 0.4 output |
| 02 | `02_create_file_format_and_stage.sql` | `CLIENT_CSV_FORMAT`, `CLIENT_DATA_STAGE` | Stage listed; `LIST` empty | Error text |
| 03 | `03_create_raw_tables.sql` | Audit, rejected-row and raw tables | Raw table has 61 columns, 0 rows | Error text |
| – | **Upload (step 5)** | Put the CSV on the stage | `LIST` shows `synthetic_enterprise_data.csv`, about 6.7 MB | Screenshot of the Snowsight upload dialog |
| 04 | `04_validate_staged_file.sql` | Checks header, shape and parse errors **before loading** | Header 57/57, 11399 data rows, 0 parse errors | Full output of every section |
| 05 | `05_copy_into_raw.sql` | Loads raw (all text) + audit row | raw rows = 11399; audit STATUS `RAW_LOADED` | COPY result, audit row |
| 06 | `06_create_typed_staging.sql` | Typed staging | stg rows = 11399; conversion errors 0 | Rows with non-empty `CONVERSION_ERRORS` |
| 07 | `07_validate_staging.sql` | Blocking checks + info checks | 0 blocking failures; audit STATUS `VALIDATED` | `V_STG_VALIDATION_RESULTS` |
| 08 | `08_create_final_tables.sql` | `APPLICATION_COMPLIANCE` | 61 columns, 0 rows | Error text |
| 09 | `09_promote_validated_data.sql` | Promotes validated rows | final 11399, rejected 0; STATUS `PROMOTED` | Gate output |
| 10 | `10_reconciliation.sql` | Proves final = file | All PASS, all diffs 0; STATUS `RECONCILED` | Any non-zero diff |
| 11 | `11_create_curated_views.sql` | `V_APPLICATION_MONTH_STATUS` | 9784 app-months; Oct: 923 apps, 300 non-compliant, 132 new, 117 resolved | Checkpoint output |
| 12 | `12_create_semantic_view.sql` | `SV_APPLICATION_COMPLIANCE_V1` | `DESCRIBE` shows 2 tables, 1 relationship | **Full error text + the line it points to** |
| 13 | `13_create_agent.sql` | `AGENT_APPLICATION_COMPLIANCE_V1` | `SHOW AGENTS` lists it | Full error text |
| 14 | `14_grant_permissions.sql` | Role `METRICS_ANALYZER_DEMO_VIEWER` | Grants listed | `SHOW GRANTS` output |
| 15 | `15_smoke_tests.sql` | Semantic-view queries vs expected values | Every test matches; 15.8 all PASS | Mismatching test numbers |

Scripts 12 and 13 are the least certain (newest Snowflake syntax). If either fails, send me the exact error; the fix is usually one clause.

## 5. Upload the CSV with Snowsight (after script 03)

1. In Snowsight choose **Ingestion → Add Data** (left navigation).
2. Choose **Load files into a stage**.
3. **Select files:** browse to `…\mock_data_setup\data\synthetic_enterprise_data.csv` (only this file).
4. Pick the **Database** `METRICS_ANALYZER`, **Schema** `MOCK_DATA`, **Stage** `CLIENT_DATA_STAGE`. Leave the path blank (the file lands at the stage root).
5. Choose **Upload**. Wait for the green confirmation.
6. In a worksheet run `LIST @METRICS_ANALYZER.MOCK_DATA.CLIENT_DATA_STAGE;`. Expect one file, `synthetic_enterprise_data.csv`, about 6,701,793 bytes. **If it appears as `…csv.gz` with a smaller size**, Snowsight compressed it: that is fine, but put the `.gz` name in the `FILES = (...)` clause of scripts 04 and 05 (both mention this).

(The menu names are from Snowsight documentation; if your account's menu differs, the equivalent is any "upload files to an internal stage" dialog. Do not use `PUT` from the web UI – it is not supported there.)

## 6. Re-running safely

Every `CREATE` is `IF NOT EXISTS`, every load is guarded by the batch id, and no script uses `FORCE`. Running a script twice does nothing destructive and inserts 0 duplicate rows. To start over see `ROLLBACK.md`.

## 7. Using the agent

After script 15: Snowsight → **AI & ML → Agents → `AGENT_APPLICATION_COMPLIANCE_V1`** → Playground. Try the questions in `agent/golden_questions.md` and compare with the expected answers.

## 8. Reference – other documents

`DATA_MODEL.md` (layers and all 57 columns), `SEMANTIC_MODEL.md` (what Cortex Analyst sees, provisional measures), `AGENT_CONFIGURATION.md`, `PERMISSIONS.md`, `ROLLBACK.md`.
