# Project context (for Claude Code)

This file is a standing summary of what this project is and what's been
built, so a new session (after context loss/compaction) can get oriented
without re-deriving everything from scratch. It's a snapshot as of
**2026-09-16** — treat it as a starting point, not ground truth; verify
against the actual code, `TODO.md`, and the CDF project itself before
relying on specifics like exact numbers or file paths.

## What this project is

Production monitoring and reporting for the **Superenvases** can-making
plant (Empresas Polar), built on **Cognite Data Fusion (CDF)**. The CDF
project is hosted through **Rockwell Automation's Data Mosaix framework**
— there is no self-managed Azure AD tenant behind it, which rules out
anything requiring Azure AD/M365 admin access (e.g. Microsoft Graph email).

The plant has two production lines:

- **Línea 1** flow: MINSTER → D&I (die & iron) → LAVADORA (washer, no CDF
  data yet) → PRINTER → NECKER/VIDEO (no CDF data yet) → ISPRAY. Always
  order machine types this way in any UI, not alphabetically.
- **Línea 3** flow: MINSTER → STANDUM (Línea 3's equivalent of D&I) →
  PRINTER → ISPRAY.

**Known plant-level data quirk**: Superenvases has a recurring **daily
power cut** (Venezuela's grid situation), roughly several hours long,
timing varies day to day. It shows up as a genuine, simultaneous data gap
across every machine/timeseries (no datapoints at all, not even comm-error
sentinel values). Don't assume a mid-day gap is a bug before checking if it
lines up with this pattern.

## Core CDF conventions used throughout

- **Shift definition**: Day shift 06:00–18:00 local, Night shift
  18:00–06:00 local, both filed under the date the shift *started* (so a
  night shift starting 9/15 stays "9/15" even past midnight). Excel's own
  labels: `1ER` = day, `2DO` = night.
- **Timezone**: fixed `UTC-4` everywhere (`LOCAL_TZ` in each function's
  `config.py`) — Venezuela doesn't observe DST, so this is a constant, not
  computed.
- **`DATA_SET_ID = 5144187181631371`** — shared across the functions below.
- Machine roster (`MACHINE_CONFIGS` in
  `functions/hourly_production_report/config.py`): 3 printers, 6 D&I
  (di11/12/14/15/17/18 — di16 has no CDF feed), 8 Standum (standum31-38), 2
  Minster (l1/l3), 13 ISpray (ispray11-15 on L1, ispray31-38 on L3) = 32
  machines total.
- Local-auth pattern: `streamlit/cdf_auth.py`'s `get_client()`/
  `get_async_client()` tries the zero-arg Fusion-style call first, falls
  back to `.env`-based client-credentials auth for local dev. Every
  `functions/*/local_test.py` uses this. `streamlit/cdf_service.py` itself
  does **not** yet (still bare `AsyncCogniteClient()`) — see TODO.

## Deployed Cognite Functions (the automated pipeline)

Three functions, in this order, each shift:

1. **`hourly_production_report`** (pre-existing, not touched much this
   session) — runs hourly, computes per-machine hourly production/downtime/
   efficiency from raw counter timeseries, writes a `Production Report`
   event per machine per hour (`external_id`:
   `report_{code}_{date_str}_{shift_code}_entry_{01..12}`), plus derived
   per-line/per-type rollup timeseries for Grafana (`LINE1_DI_PRODUCTION_
   SHIFT`, `GLOBAL_EFFICIENCY_SHIFT`, etc.). Its `calculate_hourly_counter_
   delta()` is reset-aware (a counter dropping to ~0 mid-hour = real reset,
   not noise) and drops negative comm-error sentinel readings (-1/-1001).

2. **`shift_reconciler`** (new, 2026-09-16) — scheduled **06:15/18:15
   local**. Re-runs `hourly_production_report`'s own logic (`hourly_core.py`
   here is a **copy** of that function's `handler.py`, kept in sync via
   `sync_core.py` — Cognite Functions can't import code across separate
   deployments) for all 12 hours of the shift that just ended, correcting
   any hour that was originally computed while CDF was still backfilling
   telemetry. Built after finding a real ~31% under-count on STANDUM-31's
   night-shift total, traced to exactly this. **Does NOT fix** production
   lost when the daily power-cut gap crosses a shift boundary — that's a
   structurally different, still-open problem (see `TODO.md`).

3. **`shift-excel-report-v2`** (new/rebuilt this session) — scheduled
   **06:20/18:20 local** (after the reconciler). Downloads
   `short_can_report.xlsx` ("Short Can - D&I y STD.xlsx", the customer-
   facing daily D&I/Standum report) from CDF Files, fills in the shift that
   just ended for every machine with a CDF mapping (unmapped machines —
   D&I-16, RAGS-19, RAGS-20 — stay blank), extends the file's blank-row
   scaffold a couple days ahead, and **emails the updated file via AWS SES**
   as a real `.xlsx` attachment. Idempotent (won't overwrite an
   already-filled cell) unless `force: true` is passed, e.g. after a
   reconciler correction. Email is skipped on `dry_run` and on no-op re-runs
   to avoid spamming, overridable via `send_email`. AWS creds come from
   Fusion secrets `aws-access-key`/`aws-secret-key` (Fusion's Secrets UI
   caps keys at 15 chars, lowercase+dashes only — not boto3's own longer
   names). SES identities are verified in **`us-east-2`**, not whatever an
   AWS CLI default profile says. **`EMAIL_TO` is still an internal test
   address**, not the real customer — switch once the schedule's proven
   itself over a few real shifts. The original `shift-excel-report` (v1,
   no email) is kept around with its schedule disabled, as a rollback.

**Deployment mechanics that matter**: the local-dev service principal
(`.env`) has no `functionsAcl` at all, so `client.functions.create()`/
`schedules.create()` can't be called from this environment — everything
gets deployed by hand through Fusion's UI (Build Solutions > Functions).
Functions are also **immutable once created** — no in-place code update.
The safe pattern used here is deploying a fix as a parallel `-v2` function
with its own schedule, confirming it works, then retiring the old one —
not delete-then-hope.

## Other project areas (not the focus of recent sessions)

- **`streamlit/`** — the main Streamlit app (`main.py`, `cdf_service.py`,
  `charts.py`, `config.py`), hosted in CDF Fusion's Build Solutions >
  Streamlit apps. That hosting runs **stlite** (Streamlit compiled to
  WebAssembly via Pyodide), which is why `main.py` can use top-level
  `await`. A plan exists (not started) to preview it locally via
  `@stlite/desktop` without changing `main.py` — see `TODO.md`.
- **`overview_dashboard/`** — a separate app/package whose
  `cdf_service.py`'s `load_overview()` has repeatedly served as the
  independent cross-check for hourly/shift totals computed elsewhere.
- **`grafana/`** — `dashboard_linea1.json` (done) and a general dashboard;
  Línea 3's dashboard is blocked on a diagram image from the user.
  `grafana/dashboard_general.json` is currently untracked in git.
- **Cognite Charts** (Fusion's Charts app) — no bulk-creation API exists in
  the SDK (`client.charts` doesn't exist), so these are created by hand.
  19/32 production charts done as of 2026-09-16; remaining 13 are all
  ISPRAY series. All 34 loss/downtime charts still pending.
- `anomaly_monitor/`, `data_exports/`, `notebooks/` exist in the repo but
  haven't come up in recent sessions — no summarized context to offer here.

## Git

Repo root is `cognite-sdk/` (the outer `streamlit/` folder is **not** a git
repo). Remote: `github.com/multiopti/using-cognite-python-sdk-data-modeling`,
working branch `master`. `data/` (the real customer Excel file) and
`grafana/dashboard_general.json` are deliberately left **untracked** —
that's a conscious choice made when asked, not an oversight, but also means
there's no git history to fall back on if that Excel file is ever damaged.

## Where to look next

- **`TODO.md`** (same folder as this file) — the actual up-to-date pending-work
  list; more granular and more current than this file for anything in flux.
- Each function's own `README.md` under `functions/*/` has the
  authoritative deploy/schedule/testing steps for that function.
