# shift_excel_report (Cognite Function)

Keeps `short_can_report.xlsx` ("Short Can - D&I y STD.xlsx", the customer-facing
daily D&I/Standum production log stored in CDF Files) up to date every shift:
fills in the shift that just ended for every machine CDF actually reads
(machines with no CDF mapping -- D&I-16, RAGS-19, RAGS-20 -- are always left
blank), tops up the file's blank-row scaffold so it never runs out of rows
to write into, and emails the freshly-updated file out via AWS SES.

## Files

- `handler.py` -- the `handle()` entry point and all logic.
- `config.py` -- machine map, the file's CDF Files `external_id`/`data_set_id`,
  shift/timezone constants, and SES `EMAIL_FROM`/`EMAIL_TO`/`AWS_REGION`.
  Edit this if a machine mapping changes, the D&I-15 introduction date/
  scaffold buffer need adjusting, or the email recipient changes (currently
  an internal address, not the real customer yet -- see below).
- `requirements.txt` -- pip deps for this function (`cognite-sdk`, `openpyxl`,
  `boto3`, pinned to match what's installed locally).
- `local_test.py` -- run `handle()` locally (real CDF reads, `dry_run=True`
  by default so nothing is written back to CDF Files or emailed) before
  deploying.
- `send_report_email.py` -- standalone script used to validate the SES send
  in isolation before it was wired into `handle()`. Not part of the deployed
  Function; kept for quick manual re-testing of just the email step.

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
   `local_test.py`, `send_report_email.py`, or `__pycache__` --
   `local_test.py` imports `cdf_auth`, which doesn't exist in the deployed
   function's environment, and neither is needed there (the real deployed
   Function gets its `client` argument pre-instantiated by CDF itself).
4. **AWS credentials for SES**: add secrets `aws-access-key` and
   `aws-secret-key` (an IAM user scoped to just
   `ses:SendEmail`/`ses:SendRawEmail`) in Fusion -- these names (not boto3's
   own `aws_access_key_id`/`aws_secret_access_key`) are required because
   Fusion's Secrets UI caps keys at 15 characters and only allows lowercase
   letters, digits, and dashes. `handle()` reads them from its `secrets`
   argument, which CDF injects automatically since the function signature
   declares it. Without this, `_send_report_email` falls back to boto3's
   default credential
   chain, which has nothing to find inside the deployed sandbox (no
   `~/.aws/credentials` there) and will fail.
5. Wait for the function's status to show **Ready** (can take a few minutes)
   before scheduling or test-calling it.
6. Test-call it once from the Fusion UI (or `client.functions.call()` with a
   service principal that does have `functionsAcl`) with `data: {"dry_run":
   true}` and confirm the returned summary looks right before scheduling --
   this also skips sending an email, so a first sanity check can't spam the
   inbox either.

## Scheduling (twice daily, at shift end)

**Updated schedule: 06:20 and 18:20 local** (`config.LOCAL_TZ` is fixed
`UTC-4`, no DST) -- moved from the original 06:05/18:05 to run *after*
`shift_reconciler` (see `functions/shift_reconciler/README.md`), which now
runs at 06:15/18:15 to correct any hourly events CDF was still backfilling
when they were first computed. Running this function before the reconciler
would read stale data. CDF Function schedules use cron in **UTC**, so
06:20/18:20 local is **10:20 and 22:20 UTC**:

```
cron: 20 10,22 * * *
```

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
overwrites a cell that's already filled in, unless `force: True` is also
passed:

```python
client.functions.call(
    external_id="shift-excel-report",
    data={"date_str": "20260915", "turno": "2DO", "force": True},  # overwrite already-filled cells
)
```

Use `force` after re-running `shift_reconciler` for a shift whose events
were corrected -- otherwise the idempotency check would skip cells that
already have (now-stale) values instead of overwriting them with the
corrected totals.

## Email delivery

Sent via AWS SES right after a real (non-`dry_run`) upload, as a genuine
`.xlsx` attachment (not just text) -- see `_send_report_email` in
`handler.py`. Two things worth knowing:

- **SES identity verification is per-region.** Both `EMAIL_FROM`/`EMAIL_TO`
  in `config.py` are verified in `us-east-2`, not whatever region an AWS
  CLI's default profile happens to be set to (`us-east-1`, in this case) --
  `AWS_REGION` in `config.py` is set explicitly for that reason. If the
  sender/recipient ever change, re-verify the new identities in that same
  region or update `AWS_REGION` to match wherever they're verified.
- **`EMAIL_TO` is currently an internal address, not the real customer.**
  Switch it once the automated flow has been watched run cleanly for a few
  real shifts.

To avoid re-emailing the same report on every idempotent retry/duplicate
schedule trigger, an email only goes out when this run actually wrote new
shift data (`cells_filled` non-empty) or was an explicit `force` correction
-- override either way with `data={"send_email": True}` /
`data={"send_email": False}`.
