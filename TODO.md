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
