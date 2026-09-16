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
  `C:\Users\sanch\.claude\plans\synchronous-snuggling-knuth.md`, not started):
  swap `streamlit/cdf_service.py`'s bare `AsyncCogniteClient()` for
  `cdf_auth.get_async_client()` (safe no-op change once deployed in Fusion),
  then scaffold `@stlite/desktop` in `streamlit/` so `main.py` can be
  previewed locally without modification and without a Fusion upload for
  every small change.

## Grafana / Fusion Charts

- [ ] **Línea 3 Grafana dashboard** -- waiting on a diagram image from the
  user showing that line's layout before it can be built (mirrors the
  existing Línea 1 dashboard).
- [ ] **Cognite Charts in Fusion** -- 20 of 32 production charts and all 34
  loss/downtime charts still need to be manually created (Fusion's Charts
  app has no bulk-creation API used so far).
- [ ] **Grafana equivalent of "Reporte de Producción"** -- explore building a
  per-machine drill-down dashboard in Grafana matching that Streamlit page.

## Data quality / historical analysis (explicitly deferred by user: "we will do later")

- [ ] Historical cross-check of the Excel report against independently
  computed CDF totals (beyond the two dates already spot-checked).
- [ ] Backfill/correct older data-entry issues in
  `data/Short Can - D&I y STD.xlsx` if any more are found (one FECHA/DIA
  mismatch batch was already fixed; 15 pre-existing duplicate
  (FECHA,TURNO,MÁQUINA) row groups were flagged but left untouched since
  they predate this work and their cause is unconfirmed).
- [ ] Trend analysis over the historical short-can/trimmer-jam data.
