# shift_reconciler (Cognite Function)

Re-runs `hourly_production_report`'s event-generation logic for all 12
hours of the shift that just ended, overwriting each hour's Production
Report events with freshly recomputed values now that CDF has had time to
backfill any telemetry that arrived late.

## Why this exists

Investigating a real discrepancy on 2026-09-16 (STANDUM-31's night-shift
total in the customer Excel report was ~31% lower than an independent
recompute straight from raw time series) traced back to a systemic issue:
after a ~6-hour outage, the 4 hours right after telemetry resumed were
captured by `hourly_production_report` with only partially-backfilled data
-- CDF was still catching up when that hour's schedule fired. Nothing ever
re-ran those hours once the rest of the data landed, so the stale,
under-counted values stayed in the events permanently.

This function closes that gap: scheduled a few minutes after shift-end,
before `shift_excel_report` reads the events, it recomputes and upserts
every one of the shift's 12 hours (`hours_ago=1..12`) so any hour that was
originally captured mid-backfill gets corrected before the customer report
is generated.

## Files

- `handler.py` -- `reconcile_shift()`/`handle()`, the new orchestrator that
  loops `hours_ago` 1..12.
- `hourly_core.py`, `config.py` -- **copies** of
  `functions/hourly_production_report/handler.py`/`config.py`. Cognite
  Functions can't import code across separately-deployed functions, so
  these are kept in sync via `sync_core.py` rather than hand-maintained as
  a second copy of the same business logic.
- `sync_core.py` -- copies the two files above from
  `hourly_production_report/`. **Run this before every local test and
  before rebuilding the deploy zip** -- it's not run automatically.
- `local_test.py` -- runs `handle()` locally, `dry_run=True` by default
  (computes real deltas from live CDF reads for all 12 hours, but skips
  every `events.upsert()` call).
- `requirements.txt` -- same pin as `hourly_production_report`
  (`cognite-sdk==8.10.0`).

## Testing locally

```
myenv\Scripts\python functions\shift_reconciler\sync_core.py
myenv\Scripts\python functions\shift_reconciler\local_test.py
```

12x the reads of a single hourly run (23 machines x up to 3 time series x
12 hours), so this takes noticeably longer than
`hourly_production_report`'s own local test -- expect a couple of minutes,
not seconds.

## Deploying (via Fusion UI)

Same constraint as `shift_excel_report`: the local-dev service principal
has no `functionsAcl`, so deploy through Fusion's UI
(**Build Solutions > Functions > Create function**):

1. **Name / external ID**: `shift-reconciler` for both.
2. Run `sync_core.py` first to make sure `hourly_core.py`/`config.py` match
   the current `hourly_production_report` source.
3. **Files to upload**: `handler.py`, `hourly_core.py`, `config.py`,
   `requirements.txt`. Do **not** include `local_test.py` or `sync_core.py`
   (not needed at runtime; `sync_core.py` especially shouldn't run inside
   the deployed function since it'd try to reach a sibling folder that
   doesn't exist there) or `__pycache__`.
4. Wait for status **Ready**, then test-call with `data: {"dry_run": true}`
   before scheduling.

## Scheduling

Runs once per shift, **15 minutes after shift-end**, so telemetry has time
to backfill: **06:15 and 18:15 local** = **10:15 and 22:15 UTC**
(`LOCAL_TZ` is fixed UTC-4, no DST):

```
cron: 15 10,22 * * *
```

Attach a client-credentials service principal with the same scope
`hourly_production_report`'s schedule uses (it needs to write the same
Production Report events and derived rollup timeseries).

**Also update `shift_excel_report`'s existing schedule** from `5 10,22 * * *`
to **`20 10,22 * * *`** (06:20/18:20 local) -- it must run *after* this
reconciler finishes, not before, or it'll read the same stale events this
function exists to fix. That's an edit to the existing schedule in Fusion's
Schedules tab (delete + recreate the schedule with the new cron; the
function itself doesn't need to change).

## Backfilling manually

By default `hours_ago=1..12` is relative to "now", which only lines up with
a specific past shift's 12 hours if run at (or very close to) that shift's
own end. To reconcile an already-ended shift some hours later, pass
`date_str` + `shift_code` ("day" or "night") explicitly -- hours_ago gets
recomputed for that shift's real hour boundaries relative to whenever this
actually runs:

```python
client.functions.call(
    external_id="shift-reconciler",
    data={"date_str": "20260915", "shift_code": "night", "machine_codes": ["standum31"]},
)
client.functions.call(
    external_id="shift-reconciler",
    data={"dry_run": True},  # preview only, all machines
)
```

Safe to re-run any time -- every underlying `events.upsert()` call is
idempotent (same external_id, freshest values win).
