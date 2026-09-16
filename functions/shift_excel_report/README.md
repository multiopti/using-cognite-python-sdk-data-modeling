# shift_excel_report (Cognite Function)

Keeps `short_can_report.xlsx` ("Short Can - D&I y STD.xlsx", the customer-facing
daily D&I/Standum production log stored in CDF Files) up to date every shift:
fills in the shift that just ended for every machine CDF actually reads
(machines with no CDF mapping -- D&I-16, RAGS-19, RAGS-20 -- are always left
blank), and tops up the file's blank-row scaffold so it never runs out of
rows to write into.

## Files

- `handler.py` -- the `handle()` entry point and all logic.
- `config.py` -- machine map, the file's CDF Files `external_id`/`data_set_id`,
  shift/timezone constants. Edit this if a machine mapping changes or the
  D&I-15 introduction date/scaffold buffer need adjusting.
- `requirements.txt` -- pip deps for this function (`cognite-sdk`, `openpyxl`,
  pinned to match what's installed locally).
- `local_test.py` -- run `handle()` locally (real CDF reads, `dry_run=True`
  by default so nothing is written back to CDF Files) before deploying.

## Testing locally

```
myenv\Scripts\python functions\shift_excel_report\local_test.py
```

Reads the real workbook from CDF Files, computes the last completed shift's
totals from the same hourly Production Report events
`hourly_production_report` writes, and (with `dry_run=True`) prints exactly
what would be filled/added without uploading anything. To actually write,
call `handle()` with `data={"dry_run": False}` -- or override which shift to
process with `data={"date_str": "20260915", "turno": "1ER", "dry_run": False}`
for backfilling a missed shift.

## Deploying (via Fusion UI)

The service principal used for local dev/testing (`.env` / `cdf_auth.py`) has
no `functionsAcl` capability, so `client.functions.create()` can't be called
from this environment -- deploy through Fusion's UI instead
(**Build Solutions > Functions > Create function**):

1. **Name / external ID**: `shift-excel-report` for both.
2. **Runtime**: match whatever Python runtime `hourly_production_report` uses
   (check its Fusion function settings) -- keep the two consistent.
3. **Files to upload**: `handler.py`, `config.py`, `requirements.txt` from
   this folder (`functions/shift_excel_report/`). Do **not** include
   `local_test.py` or `__pycache__` -- `local_test.py` imports `cdf_auth`,
   which doesn't exist in the deployed function's environment, and isn't
   needed there (the real deployed Function gets its `client` argument
   pre-instantiated by CDF itself).
4. Wait for the function's status to show **Ready** (can take a few minutes)
   before scheduling or test-calling it.
5. Test-call it once from the Fusion UI (or `client.functions.call()` with a
   service principal that does have `functionsAcl`) with `data: {"dry_run":
   true}` and confirm the returned summary looks right before scheduling.

## Scheduling (twice daily, at shift end)

Requested schedule: **06:05 and 18:05 local** (`config.LOCAL_TZ` is fixed
`UTC-4`, no DST). CDF Function schedules use cron in **UTC**, so that's
**10:05 and 22:05 UTC**:

```
cron: 5 10,22 * * *
```

The 5-minute offset after each shift boundary (06:00/18:00 local) gives the
last hourly Production Report event for that shift a moment to land before
this function reads it.

In Fusion: open the function > **Schedules** tab > **Create schedule**,
paste the cron expression above, and attach a client-credentials service
principal scoped at minimum to:
- `filesAcl` READ + WRITE (to download/re-upload the workbook)
- `eventsAcl` READ (to read the hourly Production Report events)
- whatever `dataSetsAcl`/scope covers `data_set_id = 5144187181631371`

This can be the same schedule service principal already used for
`hourly_production_report`'s schedule, if it already has these.

## Backfilling a missed shift

```python
client.functions.call(
    external_id="shift-excel-report",
    data={"date_str": "20260915", "turno": "1ER"},  # real write
)
client.functions.call(
    external_id="shift-excel-report",
    data={"date_str": "20260915", "turno": "1ER", "dry_run": True},  # preview only
)
```

Safe to call repeatedly for the same shift -- `_fill_shift_blanks` never
overwrites a cell that's already filled in.

## Known open item

Email delivery to the customer is intentionally not part of this Function
yet -- the file is kept current in CDF Files, but nothing sends it out. Revisit
once an email-sending mechanism is chosen.
