# hourly_production_report (Cognite Function)

Ported from `notebooks/Notebooks_dataset_220726_113831_CreateHourlyReport.ipynb`.
Computes hourly production/downtime/efficiency KPIs for each configured
machine from raw CDF time series counters, and upserts a `Production Report`
event per machine per completed hour -- the same events
`streamlit/cdf_service.py` reads and lets operators annotate.

See the top of `handler.py` for exactly what changed from the notebook
version (asset resolution, warnings, shared shift-calc helper, structured
return value, `data`-driven backfill). The original notebook is untouched.

## Files

- `handler.py` -- the `handle()` entry point and all logic.
- `config.py` -- machine list, timeseries external_ids, constants. Edit this
  when a machine is added/removed/renamed.
- `requirements.txt` -- pip deps for this function.
- `local_test.py` -- run `handle()` locally against one machine before
  deploying (uses `streamlit/cdf_auth.py` + `.env`, see the repo root
  `env.example`).

## Testing locally

```
myenv\Scripts\python functions\hourly_production_report\local_test.py
```

This runs only `di11` against the last completed hour by default (see the
`data` dict in `local_test.py`) so a test doesn't post 25 events at once.

## Deploying

```python
from cognite.client import CogniteClient
client = CogniteClient()  # or cdf_auth.get_client() locally

func = client.functions.create(
    name="hourly-production-report",
    external_id="hourly-production-report",
    folder="functions/hourly_production_report",
)
```

Wait for `func.update()` to show `status == "Ready"` (can take a few
minutes) before scheduling or calling it.

## Scheduling (hourly)

Scheduled runs have no interactive user behind them, so the schedule needs
its own client-credentials service principal (the same kind of Azure AD app
registration used for local dev in `env.example` -- ideally a dedicated one
scoped only to what this function needs, e.g. write access to Events in
`DATA_SET_ID` and read access to the relevant assets/time series):

```python
client.functions.schedules.create(
    name="hourly-production-report-schedule",
    function_external_id="hourly-production-report",
    cron_expression="0 * * * *",  # every hour, on the hour
    client_credentials={
        "client_id": "<schedule-service-principal-client-id>",
        "client_secret": "<schedule-service-principal-client-secret>",
    },
)
```

Confirm the exact `schedules.create` signature against your installed SDK
version (`help(client.functions.schedules.create)`) before relying on this --
worth double-checking since this wasn't independently verified against live
docs while porting.

## Backfilling a missed or failed hour

Call the function directly (or `handle()` locally) with `data`:

```python
client.functions.call(
    external_id="hourly-production-report",
    data={"hours_ago": 3},          # re-run the hour 3 hours before now
)
client.functions.call(
    external_id="hourly-production-report",
    data={"machine_codes": ["p11", "minster_l1"]},  # only these machines
)
```

Both can be combined in the same `data` dict.

## Known limitation carried over from the notebook

`calculate_hourly_counter_delta()` sums consecutive datapoint deltas only
between samples that fall strictly inside the hour's `[start, end)` window.
If the source signal doesn't sample exactly on the hour boundary (common for
on-change/event-driven tags), the partial gain between the true boundary and
the first in-window sample isn't captured by either adjacent hour's window.
This wasn't changed during the port since it's a KPI-calculation decision,
not a straightforward bug -- worth a closer look if the hourly numbers ever
need to reconcile exactly against a daily total.
