"""
Shift reconciler -- Cognite Function.

Re-runs hourly_production_report's own event-generation logic for all 12
hours of the shift that just ended, overwriting each hour's Production
Report events with freshly recomputed values.

Why this exists: CDF can still be backfilling telemetry (e.g. after a
power-cut data gap) at the exact moment hourly_production_report originally
computed a given hour. Investigating a real discrepancy on 2026-09-16
(STANDUM-31's night-shift total in the customer Excel report was ~31% lower
than an independent recompute from raw time series) traced back to exactly
this: the 4 hours right after a ~6-hour outage were captured with only
partial backfilled data at the time, and nothing ever re-ran them once the
rest of the data landed. Running this ~15 minutes after shift-end -- before
shift_excel_report reads the events -- gives backfilled telemetry time to
arrive and corrects those hours in place before the customer report is
generated.

hourly_core.py and config.py in this folder are COPIES of
functions/hourly_production_report/handler.py and config.py -- see
sync_core.py. Do not hand-edit them here.
"""
from datetime import datetime, timedelta

from hourly_core import LOCAL_TZ, run_all_production_reports


def reconcile_shift(client, data: dict = None) -> dict:
    """
    By default (no overrides), hours_ago=1..12 run at shift-end+15min covers
    exactly the 12 hours of the shift that just ended -- run_all_production_
    reports derives each hour window purely from "now" truncated to the
    current hour minus (hours_ago-1).

    For a manual backfill run any time AFTER shift-end+15min (e.g. fixing a
    specific already-ended shift hours later), pass date_str ("YYYYMMDD")
    and shift_code ("day" or "night") to target that shift explicitly --
    hours_ago is then computed relative to "now" for each of that shift's
    12 real hour boundaries instead of assuming "now" is right at shift-end.
    """
    data = data or {}
    dry_run = bool(data.get("dry_run", False))
    only_codes = data.get("machine_codes")
    override_date_str = data.get("date_str")
    override_shift_code = data.get("shift_code")

    if override_date_str and override_shift_code:
        shift_date = datetime.strptime(override_date_str, "%Y%m%d").date()
        shift_start_hour = 6 if override_shift_code == "day" else 18
        shift_start_local = datetime(shift_date.year, shift_date.month, shift_date.day, shift_start_hour, tzinfo=LOCAL_TZ)
        now_hour_local = datetime.now(LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
        hour_ends = [shift_start_local + timedelta(hours=i) for i in range(1, 13)]
        hours_ago_list = [int(round((now_hour_local - end).total_seconds() / 3600)) + 1 for end in hour_ends]
        hours_ago_list = [h for h in hours_ago_list if h >= 1]  # drop any hour that hasn't happened yet
    else:
        hours_ago_list = list(range(1, 13))

    totals = {"ok": 0, "dry_run": 0, "skipped": 0, "errors": 0}
    per_hour = {}
    for hours_ago in hours_ago_list:
        sub_data = {"hours_ago": hours_ago, "dry_run": dry_run}
        if only_codes:
            sub_data["machine_codes"] = only_codes
        result = run_all_production_reports(client, sub_data)
        per_hour[f"hours_ago_{hours_ago}"] = {"window": result["window"], "summary": result["summary"]}
        for k in totals:
            totals[k] += result["summary"][k]

    return {"hours_reconciled": len(per_hour), "dry_run": dry_run, "totals": totals, "per_hour": per_hour}


def handle(client=None, data: dict = None) -> dict:  # noqa: F821 - injected by CDF at runtime
    return reconcile_shift(client, data)
