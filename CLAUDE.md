# Project context (for Claude Code)

This file is a standing summary of what this project is and what's been
built, so a new session (after context loss/compaction, or a fresh chat)
can get oriented without re-deriving everything from scratch. It's a
snapshot as of **2026-09-22** — treat it as a starting point, not ground
truth; verify against the actual code, `TODO.md`, and the CDF project
itself before relying on specifics like exact numbers or file paths.

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
lines up with this pattern. When the gap crosses a shift boundary, the
catch-up telemetry lands as a "reset" event in the *following* shift and is
currently unattributable back to the shift it happened in — a known,
accepted limitation (see `TODO.md`), not something to silently "fix".

**User preferences to keep in mind**: prefers AWS over other cloud vendors
when a choice is open (used for SES email below). No Azure AD available in
this project (Data Mosaix, not self-managed Azure AD) — don't propose
Graph API/M365-admin-dependent solutions.

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
- Local-auth pattern: each app/function's own `cdf_auth.py` (`get_client()`/
  `get_async_client()`) tries the zero-arg Fusion-style call first, falls
  back to `.env`-based client-credentials auth for local dev. Every
  `functions/*/local_test.py` and every Streamlit app's `cdf_service.py`
  uses this **except** `streamlit/cdf_service.py` itself, which still uses
  a bare `AsyncCogniteClient()` — see `TODO.md`.
- **Deployment mechanics that apply to everything in Fusion**: the
  local-dev service principal (`.env`) has almost no elevated capabilities
  (no `functionsAcl`, no `groupsAcl`), so Functions/schedules/IAM groups
  can't be created or inspected from this environment — everything gets
  deployed/configured by hand through Fusion's UI. Cognite Functions are
  also **immutable once created** — no in-place code update; the safe
  pattern is deploying a fix as a parallel `-v2` (or similar) with its own
  schedule, confirming it works, then retiring the old one.

## Deployed Cognite Functions (the automated shift-report pipeline)

Three functions, in this order, each shift — **confirmed running fully
automatically since 2026-09-17** with no manual intervention:

1. **`hourly_production_report`** (pre-existing) — runs hourly, computes
   per-machine hourly production/downtime/efficiency from raw counter
   timeseries, writes a `Production Report` event per machine per hour
   (`external_id`: `report_{code}_{date_str}_{shift_code}_entry_{01..12}`),
   plus derived per-line/per-type rollup timeseries for Grafana/Streamlit
   (`LINE1_DI_PRODUCTION_SHIFT`, `GLOBAL_EFFICIENCY_SHIFT`, etc.). Its
   `calculate_hourly_counter_delta()` is reset-aware (a counter dropping to
   ~0 mid-hour = real reset, not noise) and drops negative comm-error
   sentinel readings (-1/-1001).

2. **`shift_reconciler`** — scheduled **06:15/18:15 local**. Re-runs
   `hourly_production_report`'s own logic (`hourly_core.py` here is a
   **copy** of that function's `handler.py`, kept in sync via
   `sync_core.py` — Cognite Functions can't import code across separate
   deployments) for all 12 hours of the shift that just ended, correcting
   any hour that was originally computed while CDF was still backfilling
   telemetry. Built after finding a real ~31% under-count on STANDUM-31's
   night-shift total, traced to exactly this. **Does NOT fix** production
   lost when the daily power-cut gap crosses a shift boundary — see above.

3. **`shift-excel-report-v2`** — scheduled **06:20/18:20 local** (after the
   reconciler). Downloads `short_can_report.xlsx` ("Short Can - D&I y
   STD.xlsx", the customer-facing daily D&I/Standum report) from CDF Files,
   fills in the shift that just ended for every machine with a CDF mapping
   (unmapped machines — D&I-16, RAGS-19, RAGS-20 — stay blank), extends the
   file's blank-row scaffold a couple days ahead, and **emails the updated
   file via AWS SES** as a real `.xlsx` attachment. Idempotent (won't
   overwrite an already-filled cell) unless `force: true` is passed, e.g.
   after a reconciler correction. Email is skipped on `dry_run` and on
   no-op re-runs to avoid spamming, overridable via `send_email`.
   - AWS creds come from Fusion secrets `aws-access-key`/`aws-secret-key`
     (Fusion's Secrets UI caps keys at 15 chars, lowercase+dashes only —
     not boto3's own longer names).
   - SES identities are verified in **`us-east-2`** specifically — SES
     identity verification is per-region, don't assume it matches whatever
     an AWS CLI default profile says (was `us-east-1` here, wrong region).
   - **`EMAIL_TO` in `config.py` is still an internal test address**
     (`gustavo.sanchez@ingedaca.com`), not the real customer — switch once
     you're confident in the automated schedule.
   - The original `shift-excel-report` (v1, no email) is kept around with
     its schedule disabled, as a rollback.

## Streamlit apps in CDF Fusion

Four apps, each a self-contained folder (`main.py`, `config.py`,
`cdf_service.py`, `cdf_auth.py`, sometimes `charts.py`) deployed under
Build Solutions > Streamlit apps. That hosting runs **stlite** (Streamlit
compiled to WebAssembly via Pyodide), which is why `main.py` files can use
top-level `await`.

- **`streamlit/`** — "Reporte de Producción", the main per-machine
  dashboard.
- **`overview_dashboard/`** — "Dashboard General de Producción". Its
  `cdf_service.py`'s `load_overview()` has repeatedly served as the
  independent cross-check for hourly/shift totals computed elsewhere.
- **`anomaly_monitor/`** — "Monitor de Anomalías".
- **`linea1_plant_view/`** (new) — reproduces Grafana's "Producción -
  Línea 1" canvas panel as a Streamlit page: the plant's 3D layout diagram
  with live production/scrap values overlaid near MINSTER/D&I/PRINTER/
  ISPRAY, sourced from the same `LINE1_*_SHIFT` rollup timeseries
  `hourly_production_report` already writes (no new backend needed). Box
  positions and colors (blue = producción, rose/red = merma, matching
  Grafana's own `super-light-blue`/`super-light-red` scheme) were tuned
  iteratively against real deployed screenshots — annotation boxes use an
  **explicit fixed `width`/`height`** rather than auto-sizing, because
  auto-sized boxes rendered a different footprint in Fusion's actual
  browser than in local static-image testing (font-metric differences),
  causing overlaps that weren't visible locally. If Línea 3 gets a similar
  diagram image, this app is the template to copy.

**Important deployment quirk discovered this session**: Fusion's Streamlit
code editor is **paste-only, no binary asset upload** (unlike Functions,
which accept a zip). All four apps originally hotlinked their logo from an
external Wikia URL (`LOGO_URL`), which was unreliable inside the
stlite/Pyodide sandbox and actually served WebP content despite its `.png`
extension. Fixed by embedding the logo as a **base64 string directly in
`config.py`** (`LOGO_B64`), decoded at runtime via
`st.image(io.BytesIO(base64.b64decode(LOGO_B64)), width=130)`. Images are
resized/re-encoded first to keep the embedded string a reasonable size
(the logo: ~59KB base64; `linea1_plant_view`'s background diagram, a much
bigger image: ~260KB base64 as re-encoded JPEG, down from a 1.57MB PNG).
This is now the standard technique for any image asset in a Fusion-hosted
Streamlit app — there's no other way to bundle a binary file.

## IAM / user permissions in Data Mosaix (open investigation)

Fusion shows named **Roles** (Application Developer, Applications,
Application User, Data Configurator, Data Scientist,
Data Scientist_DiagramParsing, Extractors, Operator, Project Admin), each
mapping to one or more underlying `FTDM-Grp-*` capability groups — some
atomic (one role → one group), some composite (several stacked). Only
partially mapped out; the full untruncated list of available `FTDM-Grp-*`
building blocks hasn't been seen yet.

A custom "Flows-only" group was created (auto-named
`FTDM-Operator_170926_175527`, a rename to something like `FTDM-Grp-
FlowsOperator` was proposed and explicitly deferred) intended to allow
Flows/Charts/Canvas/Custom Applications with Time Series + Events
read/write, but without Data Fusion (Explore) or Admin access. A test
login confirmed the actual data loads correctly under it.

**Real unresolved problem**: a user believed to be restricted to
"Application User" could still **edit** Streamlit apps, not just view
them. Root cause is almost certainly that **CDF group membership is
additive** (effective access = union of every group a user belongs to) —
Streamlit apps are stored as CDF Files, so if that user still belongs to
any broader group with `filesAcl:WRITE` (e.g. `Applications` or `Data
Configurator`, both `files: read | write`) from before, adding
`Application User` on top doesn't remove that access. **Not yet fixed** —
needs someone to open Access Management, check that user's full group
membership list (not just confirm the narrow role is present), and remove
whatever broader group is still granting write access. Flagged as
deserving a proper pass on user/role setup in general, not a one-off fix.

## Other project areas

- **`grafana/`** — `dashboard_linea1.json` (done, source for
  `linea1_plant_view` above) and a general dashboard; Línea 3's dashboard
  is blocked on a diagram image from the user.
  `grafana/dashboard_general.json` is currently untracked in git.
- **Cognite Charts** (Fusion's Charts app) — no bulk-creation API exists in
  the SDK (`client.charts` doesn't exist), so these are created by hand.
  24/32 production charts done as of 2026-09-17; remaining 8 are all
  ISPRAY Línea 3 series. All 34 loss/downtime charts still pending.
- `anomaly_monitor/` is now documented above (Streamlit apps section).
  `data_exports/`, `notebooks/` exist in the repo but haven't come up in
  recent sessions — no summarized context to offer here.

## Git

Repo root is `cognite-sdk/` (the outer `streamlit/` folder is **not** a git
repo). Remote: `github.com/multiopti/using-cognite-python-sdk-data-modeling`,
working branch `master` (currently at `194fa30`). `data/` (the real
customer Excel file) and `grafana/dashboard_general.json` are deliberately
left **untracked** — a conscious choice made when asked, not an oversight,
but also means there's no git history to fall back on if that Excel file
is ever damaged.

## Where to look next

- **`TODO.md`** (same folder as this file) — the actual up-to-date pending-work
  list; more granular and more current than this file for anything in flux.
  Key open items right now: the cross-shift power-cut gap (deferred, not
  actively worked), switching `EMAIL_TO` to the real customer, the IAM
  additive-group-membership bug above, remaining Cognite Charts (8 ISPRAY
  L3 + all 34 loss/downtime), and the never-started local-Streamlit-testing
  plan (`@stlite/desktop`).
- Each Cognite Function's own `README.md` under `functions/*/` has the
  authoritative deploy/schedule/testing steps for that function.
