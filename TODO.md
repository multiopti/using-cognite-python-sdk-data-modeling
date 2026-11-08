# TODO

Pending work tracked across sessions. Update as items are picked up/finished.

## shift_excel_report / shift_reconciler (customer Excel report automation)

- [x] First scheduled run verified (2026-09-16 06:05:12 local, matched the
  original cron exactly).
- [x] **shift_reconciler** built and deployed -- re-runs
  `hourly_production_report`'s logic for all 12 hours of a shift shortly
  after it ends, fixing hours that were originally computed while CDF was
  still backfilling telemetry. Scheduled at 06:15/18:15 local;
  `shift-excel-report`'s schedule moved to 06:20/18:20 local so it always
  reads post-reconcile data. Both redeployed 2026-09-16 with the current
  code (including `shift_excel_report`'s new `force: true` override for
  re-filling an already-filled shift after a correction).
- [x] **First fully automatic, untouched pipeline run confirmed
  (2026-09-17).** Both shifts of 9/16 (day + night) were filled with no
  manual intervention -- file `last_updated` matched the 06:20 schedule
  exactly, and both shifts' totals independently cross-checked against raw
  timeseries (D&I-11 within ~2.6%, normal boundary rounding; STD-31 exact
  match). The large day-vs-night gap that day (e.g. D&I-11 35,839 vs
  110,721) is genuine higher night production, not a reconciliation bug.
- [ ] **Cross-shift-boundary production loss from the daily power cut is
  NOT fixed by shift_reconciler** (found + confirmed 2026-09-16). The
  plant's known recurring power cut (see
  `superenvases-daily-power-cuts` memory) can knock a machine's telemetry
  out for most of a shift; when power returns, the counter's first new
  reading is a single jump that lands in whichever shift the power came
  back during -- e.g. STD-31/32/33/34/36/37 and D&I-14/17 went silent
  2026-09-15 08:10-18:00 (day shift), and the catch-up value showed up as a
  "reset" event at the very start of the night shift instead. No per-hour
  or per-shift windowed calculation can attribute that jump back to the
  shift it actually happened in -- this is a structurally different problem
  than the backfill-timing issue shift_reconciler solves, and would need
  the counter-delta logic to detect "this shift's first reading is way
  higher than the last shift's last known reading" and split the gain
  across the gap. Explicitly deferred by the user ("it is ok, this is
  something we already know") -- revisit if the customer needs shift-level
  numbers to be accurate through a power-cut day, not just close.
- [x] **Email delivery to the customer.** Built on AWS SES (user's
  preference, see `user-prefers-aws` memory), wired into `handle()` via
  `_send_report_email` -- sends the freshly-updated `.xlsx` as a real
  attachment right after upload, skipped on `dry_run` and on idempotent
  no-op re-runs (nothing in `cells_filled`, no `force`) to avoid spamming.
  Deployed as `shift-excel-report-v2` (parallel to the original
  `shift-excel-report`, kept disabled as a fallback) with AWS credentials
  as Fusion secrets `aws-access-key`/`aws-secret-key` (names dash-separated
  and ≤15 chars -- Fusion's Secrets UI requirement, different from boto3's
  own `aws_access_key_id`/`aws_secret_access_key`). Verified end-to-end
  2026-09-16 via a real deployed test call -- email received with correct
  attachment and shift-specific subject line. **`EMAIL_TO` in config.py is
  still an internal test address (`gustavo.sanchez@ingedaca.com`), not the
  real customer** -- switch once the automated schedule has run cleanly a
  few times.

## Local dev tooling

- [ ] **Local testing for the CDF-hosted Streamlit app** (plan saved at
  `C:\Users\sanch\.claude\plans\synchronous-snuggling-knuth.md`): the
  `cdf_service.py` swap to `cdf_auth.get_async_client()` is **done**
  (2026-10-19, commit `de887a7`), and `planta_local/run_app.py` already runs
  `main.py` unmodified on a local Streamlit server -- which covers most of
  the original need. Remaining (optional): scaffold `@stlite/desktop` if a
  preview that matches Fusion's Pyodide runtime exactly is still wanted.
  **The updated `streamlit/cdf_service.py` and `main.py` still need to be
  pasted into the Reporte de Producción app in Fusion and republished** (no
  behaviour change there, but keeps Fusion and the repo in sync).

## Plant-floor server (planta_local/) -- built + tested locally 2026-10-19

Serves Línea 1 / Línea 3 plant views and the read-only Reporte de Producción
on the plant LAN (TV rotation on :8500, apps on :8501-8503), without a Fusion
login. Code committed in `de887a7`; see `planta_local/README.md`.

- [ ] **Install on the plant's Windows server** with
  `planta_local\install_service.ps1` (as Administrator). Need from the plant
  first:
  - whether the server has internet access to
    `aw-was-gp-001.cognitedata.com` and the identity provider, or needs a
    proxy (configure it for the SYSTEM account, which runs the task);
  - whether the TV gets a mini-PC (recommended: Edge in `--kiosk` mode) or is
    a Smart TV with its own browser (iframe support is hit-and-miss);
  - whether the `.env` service account can be **read-only** (time series +
    events), since every operator shares it.
- [ ] After installing: verify all four URLs from another PC on the plant
  network, and that the scheduled task restarts the server after a reboot.
- [ ] Stop the local test server on this PC (ports 8500-8503) once it's no
  longer needed for demos.

## Plant-floor data WITHOUT CDF: Node-RED / Optix (started 2026-11-07)

Client decision: the plant-floor Streamlit server must read local plant data, not CDF.
Files in `E:\source\repos\streamlit\node-red\` (outside this repo):
- The Optix project (NodeId source of truth) is
  `C:\Users\sanch\Documents\Rockwell Automation\FactoryTalk Optix\Projects\Superenvases`.
- Optix OPC UA endpoint: `opc.tcp://10.86.193.3:59100`.
- Shifts are 06:00–18:00 / 18:00–06:00, the same as the PLC counter resets and CDF.

- [x] **`flows_planta.json`: plant Node-RED flow, ready to import**, built from the July plant flow. It has:
  - 6–6 shifts and the fixed hourly logic (`-1`/`-1001` shown as N/A, correct hour after a gap and first hour of the shift);
  - Printer ACUM read every 5 min, and the new IP;
  - the ISPRAY L3_31 NodeId fixed (it was reading L3_32);
  - Standum (prod, short cans, trimmer jams) and ISPRAY ACUM tabs;
  - 65 matrices, every NodeId verified against the Optix project;
  - `GET /get-printer-data` (Excel macro, tested) and `GET /api/data_week` (for the local Streamlit server).
- [ ] Deploy `flows_planta.json` in the plant: import replacing the current flow, Deploy, reselect the shift in each dashboard. Then check that the OPC UA nodes show connected.
- [x] `Reporte_macro_http_6-6.xlsm`: report workbook with 6–6 hour labels on all 4 sheets and J2 = `6AM-6PM`. Not yet opened in Excel to confirm, because Excel COM is broken on this PC.
- [ ] Excel macro fixes:
  - URL `localhost` -> the Node-RED PC's IP (put it in a cell);
  - send the date as `Format(G2, "yyyy-mm-dd")` (it currently depends on Windows' locale);
  - read the parameters from PRINTERS, not the active sheet;
  - add a dropdown on J2 (`6AM-6PM` / `6PM-6AM`).
- [ ] D&I and Minster have NO weekly matrices in the Optix (only live tags). Either the Optix `TimeUpdater` adds them, or the local server records the live values itself.
- [x] **Local Streamlit server reads Node-RED, not CDF** (2026-11-08):
  - `planta_local/nodered_data.py`, `local_services/{plant_view,reporte}/cdf_service.py`, and `run_app.py` with `PLANT_DATA_SOURCE` (nodered by default, cdf optional).
  - Only the last week, straight from `/api/data_week` (no SQLite); hourly; read-only observations; Node-RED status line.
  - Tested:
    - report fields identical to the CDF function (11 cases, all 5 types);
    - 12-hour data matches the synthetic data;
    - all 3 apps run via `run_app.py` with no exceptions.
  - Still to check: view it in a browser (`planta_server.py`).
- [ ] (old plan, superseded by the above) Local Streamlit server (`planta_local/`):
  - a collector reading `/api/data_week` (or the Optix OPC UA directly), with history in SQLite;
  - a local `cdf_service.py` per app, with `main.py` unchanged.
  - Still to confirm with the client: whether reading the Optix OPC UA directly is acceptable.

## plant_simulation: Optix copy fed by CDF history (2026-11-08)

`E:\source\repos\streamlit\plant_simulation\` is a copy of the plant Optix project with no PLC and no cloud access. See `replay_data/README.md`.

- [x] Copy made: no `.git`, no certificates/keys, Data Mosaix secret blanked.
- [x] Simulation wiring:
  - 213 model variables no longer read the PLC;
  - TimeUpdater reads the model instead of PLC tags;
  - `CdfReplay` NetLogic: history shifted by whole weeks, plus a 7-day prefill of the 65 matrices.
- [x] The NetSolution builds with `dotnet build` (0 errors) against FT Optix Studio 1.6.2.36.
- [x] 21 days of history exported (139 tags, about 2M points).
- [ ] Open in FT Optix Studio, run the emulator and check the `CdfReplay` Status and logs. Not run yet.
- [x] Cloud publishers removed (`remove_cloud.py`):
  - the MQTT client, `Model/PushDataMosaix` and the Data Mosaix store;
  - the Data Mosaix connector's code, DLLs, NuGet packages and `config.yml`.
  - Clean build: 0 errors, 0 warnings.
- [x] Runtime checked (2026-11-08):
  - CdfReplay loaded the history and prefilled 65 matrices;
  - 6 tags read over OPC UA match the history;
  - the only errors were the absent PLC.
- [x] EtherNet/IP driver unloaded and `*_ANT` links cut (`disable_plc.py`). Nothing links to the PLC now.
- [x] CdfReplay `Mode`:
  - Synthetic (default): clean production from `rates.csv`, for testing;
  - Replay: real history, with `-1` after `StaleMinutes` without data.
  - Builds with 0 errors and 0 warnings.
  - Verified in the emulator (2026-11-08 11:17), Synthetic mode:
    - 0 errors in the log;
    - 8 tags over OPC UA match the formula;
    - 3 matrices: 167/167 hours match the formula.
  - Studio needed `Superenvases.optix.design` set to `Nodes: []` once the TagImporter was gone.
- [x] **D&I and Minster weekly matrices** added to plant_simulation (`add_di_minster_matrices.py`):
  - 22 matrices (D&I prod/short cans/trim × 6, Minster strokes per shift and per coil × 2);
  - TimeUpdater now fills 87; Minster folders made retentive; CdfReplay pre-fills all 87;
  - deterministic NodeIds; verified (paths, lists, unique ids) and builds with 0 errors.
- [x] Emulator run:
  - 87 matrices pre-filled.
  - TimeUpdater wrote the 15:00 slot at 15:59 (2026-11-08) in old and new (D&I, Minster) matrices: 10/10 match the synthetic values, read via Node-RED.
- [ ] Note: a killed Node-RED leaves its OPC UA sessions open until they time out, so the server can refuse new clients (BadTooManySessions) even with only 13 live. Stop Node-RED cleanly in the plant.
- [x] Node-RED (`flows_planta.json`): D&I PROD / D&I LATAS CORTAS / D&I TRANC TRIM / MINSTER tabs (keys `DInn`, `DInn_LATAS_CORTAS`, `DInn_TRANC_TRIM`, `MINSTER_Lx_GOLPES_TURNO|BOB`). 87 matrices, NodeIds verified against plant_simulation. Tested via the local Node-RED: `/api/data_week` returns 87 keys, and the 22 new ones match 167/167 hours.
  - The plant's Optix needs `add_di_minster_matrices.py --mode plant` first, or those 4 tabs will fail to read.
- [x] **Dashboard pages for STANDUM, D&I and MINSTER** (`node-red/add_dashboard_pages.py`, cloned from the ISPRAY page):
  - pages /page3, /page4, /page5;
  - each page has its own globals (`<prefix>_select/_turno/_days_ago`) and its own export (`data_<prefix>.xlsx`);
  - Minster shows strokes per hour plus the raw coil counter.
  - Tested: tables match the synthetic data for both shifts; the Excel function handles N columns; the local Node-RED serves all 5 pages.
- [x] **Calendar instead of "Dia anterior"** on all 5 pages (`node-red/date_picker_pages.py`):
  - `ui-text-input` in date mode;
  - "Validar fecha" accepts yesterday to 6 days ago, otherwise shows a red notification with the allowed range and resets the calendar;
  - global `<page>_date`; the calendar starts on yesterday;
  - tables show N/A for hours not finished yet.
  - Tested (validation, default date, N/A at 03:30, regressions); deployed in the local Node-RED. Still to check in a browser.
- [ ] Possible later: "Guardar datos" files could include the date, shift and machine in their names (today each page overwrites one file).
- [x] PRINTER and ISPRAY pages no longer share `turno`/`days_ago` (`node-red/separate_page_globals.py`). They now use `printer_turno`/`printer_days_ago` and `ispray_turno`/`ispray_days_ago`, so all 5 pages are independent. Tested; deployed in the local Node-RED.
- [x] **One OPC UA client per tab** (`node-red/restructure_opcua_clients.py`): 87 sessions -> 13.
  - Why: the Optix OPC UA server allows about 100 sessions (it refused the 101st with BadTooManySessions). A killed Node-RED leaves its sessions open until they time out, so with 87 clients a single restart overflowed the server.
  - Each tab's function maps NodeId -> key; the keys are unchanged.
  - Verified with `node-red/verify_flow.py` against both Optix projects, and live: 13 connections, 87 keys, values correct.
- [ ] Plant project: apply with `add_di_minster_matrices.py --project <copy of plant project> --mode plant`, then deploy to the Edge module. Decide with the client first.
  - **Plan agreed 2026-11-08.** Dry run on a copy: 7 files, additions only (5 model folders + Retentivity + TimeUpdater). The new matrices start at -1 (fix a).
  - [x] Step 1: full backup of the plant project at `C:\Users\sanch\Documents\Rockwell Automation\FactoryTalk Optix\Projects_backup\Superenvases_20261108_1444` (3,250 files, verified by hash).
  - [x] Step 2: initial value -1 (`{"Type":6,"Dimensions":[7,24],"Body":[...]}`) is in the script. Confirmed in the emulator on 2026-11-08 15:20: a test matrix read Int32 [7,24] with 168 × -1, status Good. The test matrix was removed afterwards.
  - Studio's build can exceed its timeout and still report "built successfully" with no `bin\Superenvases.dll`. Before any deploy, check that the DLL exists; after the deploy, check the log for "Unable to find the .NET assembly". In the plant that would stop TimeUpdater **and** the push to CDF.
  - [x] Step 3 (2026-11-08): **applied to the real plant project**.
    - Exactly 7 files changed, additions only, byte-identical to the reviewed dry run.
    - TimeUpdater: 87 calls; every source exists, including the 12 D&I PLC tags.
    - 22 matrices start at -1; Minster folders retentive; no duplicate ids.
    - C# compiles (checked on a copy); `flows_planta.json` matches all 87 NodeIds.
  - [ ] Steps 4-7 **at the next plant visit** (remote access is not possible). Follow `node-red/plant_visit_checklist.md`: build and check the DLL, deploy to the Edge, check the log / CDF / OPC UA / first :59, back up and import the Node-RED flow.
- [x] Local Node-RED in `node-red/local_sim` (Node-RED 4.1.17, `npm start`, 127.0.0.1:1880), running `flows_planta.json` against the emulator. Tested 2026-11-08:
  - `/api/data_week` returns 65 matrices, matching the emulator 167/167 hours;
  - `/get-printer-data` returns the expected 12 hourly values, with no CR, for both date formats;
  - out-of-range and invalid-line errors work.
  - Matrices arrive as `{"0":..,"167":..}` objects.
- [ ] Point a local Node-RED at `opc.tcp://localhost:59100` and test `flows_planta.json` end to end.

## Plant telemetry

- [x] **`tr_raw_to_datapoints_superenvases` (id 404926) stopped writing on
  2026-10-28 16:01** after the plant network repair: the edge started
  publishing 3 new tags (`PRINTER_L1/L31/L32_LAT_SOP_ACT_MAN`) with no time
  series, so every job failed with "Time series not found" and CDF blocked
  the schedule. Fixed same day: created the 3 `..._DISP` time series
  (mirroring their sibling PRINTER series' data set/asset/description) and
  changed the query to `JOIN _cdf.timeseries`, so an unknown tag is skipped
  instead of failing the job. New tags still need their time series created
  by hand -- RAW data is backfilled automatically once it exists.
- [ ] **Make that transformation incremental** (`is_new()` on the RAW
  table). It re-reads the whole `raw_mqtt_messages` table every 5 min; runs
  now take >5 min, so ~half of all runs since 2026-10-27 failed with "A job
  already runs for this transform". Changes how backfill works (only new
  RAW rows get processed), so agree on it with the user before doing it.
  Stopgap applied 2026-10-29: schedule changed `*/5` -> `*/10 * * * *`
  (runs took 237-561 s), which stops the overlap failures but not the
  growth -- runs will keep getting longer as the RAW table grows.
  Set back to `*/5` the same day at the user's request (after the partial
  RAW cleanup below) -- check job durations stay under 5 min.
- [x] **RAW cleanup of `raw_mqtt_messages` finished 2026-10-31** (second
  pass deleted the remaining 179,010 keys, resolved from CDF and
  intersected with the backup). Table now ~83k rows, oldest 2026-10-22
  08:49; transformation runs dropped to 16-42 s. It grows ~9k rows/day, so
  either repeat this cleanup every few months (`utils/backup_raw.py`, then
  `utils/delete_old_raw.py`) or do the `is_new()` change above. Original
  notes:
- **RAW cleanup of `raw_mqtt_messages` paused halfway (2026-10-29).**
  Full backup verified (603,733 rows, 22.5 MB):
  `data_exports/raw_backup/db_superenvases_raw.raw_mqtt_messages_20261029_0839.jsonl.gz`
  (git-ignored). User confirmed deleting the 538,010 rows with
  last_updated_time before 2026-10-22 08:49 (-04), keeping the last 7 days;
  all 137 tags in them already had time series, so nothing is lost from
  CDF. Stopped at ~350,000 deleted (user had to leave). To resume: rerun
  the same delete-by-key-from-backup approach for those 538,010 keys
  (re-deleting already-gone keys is harmless), then count the remaining
  rows and check the next transformation run's duration.

- [ ] **Machines have been sending only error values since 2026-10-16**, so
  every app shows 0 production. The edge heartbeat is still arriving
  (last seen 2026-10-19 20:42), so the edge device is alive and the problem
  is the PLC/tag reads on the plant side -- needs someone on site to check
  the PLC connection in the edge/OPC configuration.

## Grafana / Fusion Charts

- [ ] **Línea 3 Grafana dashboard** -- waiting on a diagram image from the
  user showing that line's layout before it can be built (mirrors the
  existing Línea 1 dashboard).
- [ ] **Cognite Charts in Fusion** -- 24 of 32 production charts done as of
  2026-09-17 (IPSPRAY_L1_11-15 finished). Remaining 8 production charts, all
  ISPRAY Línea 3: `IPSPRAY_L3_31/32/33/34/35/36/37/38_PROD_ACT_DISP`. All 34
  loss/downtime
  charts still pending too. Confirmed there's no Charts API in the SDK
  (`client.charts` doesn't exist) -- has to stay a manual Fusion UI task.
- [ ] **Grafana equivalent of "Reporte de Producción"** -- explore building a
  per-machine drill-down dashboard in Grafana matching that Streamlit page.

## Streamlit apps -- hotlinked logo

- [x] **Broken logo image fixed in all 3 live Streamlit apps** (2026-09-18):
  `streamlit/` (Reporte de Producción), `overview_dashboard/` (Dashboard
  General), `anomaly_monitor/` (Monitor de Anomalías) were all hotlinking
  the Empresas Polar logo from an external Wikia URL
  (`LOGO_URL` -- unreliable inside Fusion's stlite/Pyodide sandbox, and the
  URL actually served WebP content despite its `.png` extension). Fusion's
  Streamlit code editor has no binary-asset upload (code-paste only, no
  Files-style upload like Functions' zip), so the fix embeds the logo as a
  base64 string (`LOGO_B64` in each app's `config.py`) decoded at runtime
  via `st.image(io.BytesIO(base64.b64decode(LOGO_B64)), width=130)`.
  Verified locally in all three; needs the updated `config.py`/`main.py`
  pasted into each app in Fusion and republished to take effect there.

## IAM / user & role permissions (needs deeper investigation)

- [ ] **Understand Data Mosaix's Role -> Capability Group mapping properly.**
  Roles shown in Fusion (Application Developer, Applications, Application
  User, Data Configurator, Data Scientist, Data Scientist_DiagramParsing,
  Extractors, Operator, Project Admin) each map to one or more underlying
  `FTDM-Grp-*` capability groups -- some atomic (one role -> one group),
  some composite (several groups stacked, e.g. `Data Scientist_
  DiagramParsing` = base Data Scientist groups + `FTDM-Functions` +
  `FTDM-Grp-Chart` + 7 more). Only partially mapped out from what was
  visible on-screen (several rows were truncated with "..." / "+N") --
  worth getting the full untruncated list of available `FTDM-Grp-*`
  building blocks before hand-picking raw ACLs for any new role again.
- [ ] **Created a new custom "Flows-only" group** (`FTDM-Operator_
  170926_175527`, auto-named -- rename to something like `FTDM-Grp-
  FlowsOperator` was proposed and explicitly skipped for now) intended to
  allow running existing Flows plus Charts/Canvas/Custom Applications, with
  Time Series + Events read/write, but WITHOUT Data Fusion (Explore) or
  Admin access. A friend's test-user login confirmed the actual app data
  loads correctly under this group (charts/dropdowns worked for STANDUM32).
- [ ] **Real, more important problem found (2026-09-20): a user believed to
  be restricted to "Application User" could still EDIT Streamlit apps**,
  not just view them. Root cause is almost certainly that CDF group
  membership is additive (effective access = union of every group a user
  belongs to) -- Streamlit apps are stored as CDF Files, so if this user
  still belongs to any broader group with `filesAcl:WRITE` (e.g.
  `Applications` or `Data Configurator`, both `files: read | write`) from
  before, adding `Application User` on top doesn't remove that. **Not yet
  fixed** -- needs someone to open Access Management, check this specific
  user's FULL group membership list (not just confirm the intended narrow
  role is present), and remove whatever broader group is still granting
  write access. This deserves a proper pass on user/role setup in general,
  not just a one-off fix for this one person.
- [ ] Testing group permissions via the API (service principal /
  `client.iam.token.inspect()` + exercising real operations) was explored
  as a way to validate a new group's access without provisioning a full
  interactive user, but was skipped -- creating a spare service principal
  in this Rockwell Data Mosaix setup was judged about as hard as creating a
  user. Revisit if that ever gets easier, since it's a faster/cleaner way
  to validate a role's actual capabilities than asking someone to log in
  and click around.

## Data quality / historical analysis (explicitly deferred by user: "we will do later")

- [ ] Historical cross-check of the Excel report against independently
  computed CDF totals (beyond the two dates already spot-checked).
- [ ] Backfill/correct older data-entry issues in
  `data/Short Can - D&I y STD.xlsx` if any more are found (one FECHA/DIA
  mismatch batch was already fixed; 15 pre-existing duplicate
  (FECHA,TURNO,MÁQUINA) row groups were flagged but left untouched since
  they predate this work and their cause is unconfirmed).
- [ ] Trend analysis over the historical short-can/trimmer-jam data.

## Dev PC housekeeping (C: drive)

C: went down to 0.28 GB free on 2026-10-19; now ~11 GB after clearing caches,
old GitHub Desktop/Playwright versions and uninstalling WSL + the Dev
Containers VS Code extension. Rockwell data under `C:\Users\Public\Documents`
and `C:\Program Files (x86)\Rockwell Software` must stay on C:.

- [ ] Run Windows' own cleanup as Administrator (`cleanmgr` → "Limpiar
  archivos del sistema" → Windows Update cleanup, or
  `Dism /Online /Cleanup-Image /StartComponentCleanup`) -- likely 2-5 GB.
- [ ] Clear Chrome's cached images/files (~0.6 GB) from Chrome settings.
- [ ] Decide whether SQL Server (1.1 GB), OpenSSL (0.8 GB) and Postman
  (0.5 GB) are still needed; uninstall the ones that aren't.
- [ ] Optional: turn off the leftover "Subsistema de Windows para Linux" /
  "Plataforma de máquina virtual" Windows features (needs admin + reboot).
