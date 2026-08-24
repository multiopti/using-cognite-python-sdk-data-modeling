"""
Timeseries anomaly detector -- Cognite Function.

Scans the same raw counters `hourly_production_report` reads, looking for
five patterns per timeseries per hour:

1. RESET_TO_ZERO      -- counter genuinely reset (dropped to ~0 mid-hour).
2. NONZERO_DECREASE   -- counter dropped but NOT to zero: the exact class of
   sensor/telemetry noise that used to get misread as "the counter reset,
   so the new reading IS the hourly total" (see the `_RESET_TO_ZERO_EPS`
   fix in hourly_production_report/handler.py). Surfacing it here as its
   own event means it's visible even on machines/hours where it doesn't
   happen to produce an obviously-wrong downstream KPI.
3. NEW_WEEKLY_MAX     -- this hour's value is higher than any hour in the
   trailing week for the same timeseries.
4. SLOW_RUNNING       -- production-type metrics only (see WATCHED_TIMESERIES'
   `direction`): the machine WAS producing this hour (current_value > 0),
   just well below its normal per-shift running speed. A fully stopped
   machine (current_value == 0) is a different situation and doesn't
   trigger this pattern -- "slower than usual" means reduced throughput
   while running, not not running at all.
5. EXCESS_SCRAP       -- scrap/waste-type metrics only: this hour's value is
   well above the machine's normal per-shift rate (more defects is the bad
   direction here, not less).

Patterns 4-5 share one baseline concept: for a given machine and shift
(day/night), the "normal speed" is the average of that metric across only
the *active* hours in the trailing BASELINE_WINDOW_DAYS -- active meaning
the machine's own primary production field (see PRIMARY_FIELD) was > 0
that hour. Idle hours are excluded from training the baseline (so a quiet
night doesn't drag the reference number down and make every idle hour
look "slow" by comparison against a mixed day/night average) but a
currently-idle hour during a normally-active shift is still compared
against that baseline and can still be flagged -- only the *training*
data excludes idle hours, not the hour being checked.

Design choice: patterns 1-2 need a fresh look at this hour's raw
datapoints (the same step-by-step scan hourly_production_report already
does internally, just not exposed as its own signal). Patterns 3-5 don't
need raw data at all -- they read the *already computed, already
bug-fixed* per-hour values (and each event's own "shift" field) straight
out of the existing Production Report events hourly_production_report
writes, for the trailing BASELINE_WINDOW_DAYS. That keeps this function
fully independent of (and zero risk to) the live hourly_production_report
function -- no shared code, no shared deploy -- while still reusing its
validated numbers instead of re-deriving a week of history from raw
counters.

Schedule this a few minutes after hourly_production_report's own hourly
schedule (e.g. "5 * * * *" vs its "0 * * * *"), so the current hour's
Production Report event already exists when patterns 3-5 look for it.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta

from cognite.client.data_classes import EventWrite

from config import (
    BASELINE_WINDOW_DAYS,
    DATA_SET_ID,
    EXCESS_SCRAP_RATIO,
    LOCAL_TZ,
    MACHINE_CODE_METADATA_FIELD,
    MACHINE_CONFIGS,
    PRIMARY_FIELD,
    PRODUCTION,
    PRODUCTION_REPORT_SUBTYPE,
    RESET_TO_ZERO_EPS,
    SCRAP,
    SLOW_RUNNING_RATIO,
    WATCHED_TIMESERIES,
)


def _resolve_asset_ids(client, configs):
    """One batched lookup for all machines' asset ids, instead of one call
    per machine per run (same pattern as hourly_production_report)."""
    ext_ids = [c["asset_ext_id"] for c in configs]
    assets = client.assets.retrieve_multiple(external_ids=ext_ids, ignore_unknown_ids=True)
    return {a.external_id: a.id for a in assets}


def _hour_window(hours_ago: int):
    """Same window semantics as hourly_production_report: the hour that
    ended `hours_ago` hours before now, in LOCAL_TZ."""
    now_local = datetime.now(LOCAL_TZ)
    hour_end_local = now_local.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_ago - 1)
    hour_start_local = hour_end_local - timedelta(hours=1)
    start_ms = int(hour_start_local.timestamp() * 1000)
    end_ms = int(hour_end_local.timestamp() * 1000)
    return start_ms, end_ms, hour_start_local


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def _scan_for_reset_and_noise(client, ts_external_id: str, start_ms: int, end_ms: int):
    """Step-by-step scan of this hour's raw datapoints. Returns a list of
    (pattern, timestamp_ms, prev_val, curr_val) tuples -- one per downward
    step found, classified as RESET_TO_ZERO or NONZERO_DECREASE."""
    found = []
    try:
        dps = client.time_series.data.retrieve(
            external_id=ts_external_id, start=start_ms, end=end_ms, limit=None, ignore_unknown_ids=True,
        )
    except Exception:
        return found

    if not dps or len(dps) < 2:
        return found

    for i in range(1, len(dps)):
        prev_val = _safe_float(dps[i - 1].value)
        curr_val = _safe_float(dps[i].value)
        if curr_val - prev_val < 0:
            pattern = "RESET_TO_ZERO" if curr_val < RESET_TO_ZERO_EPS else "NONZERO_DECREASE"
            found.append((pattern, dps[i].timestamp, prev_val, curr_val))
    return found


def _production_report_history(client, machine_type: str, machine_code: str, start_ms: int, end_ms: int):
    """Events for this machine in [start_ms - BASELINE_WINDOW_DAYS, end_ms],
    split into (current_hour_event_or_None, list_of_baseline_events)."""
    subtype = PRODUCTION_REPORT_SUBTYPE[machine_type]
    code_field = MACHINE_CODE_METADATA_FIELD[machine_type]
    lookback_ms = start_ms - BASELINE_WINDOW_DAYS * 24 * 60 * 60 * 1000

    events = client.events.list(
        type="Production Report",
        subtype=subtype,
        start_time={"min": lookback_ms, "max": end_ms},
        limit=1000,
    )
    code_value = machine_code.lower() if code_field == "printer_code" else machine_code.upper()
    matching = [e for e in events if (e.metadata or {}).get(code_field) == code_value]

    current = None
    baseline = []
    for e in matching:
        if e.start_time == start_ms:
            current = e
        elif e.start_time < start_ms:
            baseline.append(e)
    return current, baseline


def _extract_metric(event, field: str) -> float | None:
    if event is None:
        return None
    val = (event.metadata or {}).get(field)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _shift_of(event) -> str | None:
    if event is None:
        return None
    return (event.metadata or {}).get("shift")


def _active_same_shift_baseline(baseline_events, current_shift: str | None, primary_field: str, target_field: str) -> list[float]:
    """Baseline training samples for one metric: same shift as the current
    hour, and only hours where the machine's own primary production field
    was actually running (> 0) -- so idle hours don't drag the "normal
    speed" reference down (or, for scrap metrics, don't get counted as
    "zero defects" when really the machine just wasn't on)."""
    if current_shift is None:
        return []
    values = []
    for e in baseline_events:
        if _shift_of(e) != current_shift:
            continue
        primary_val = _extract_metric(e, primary_field)
        if primary_val is None or primary_val <= 0:
            continue
        target_val = _extract_metric(e, target_field)
        if target_val is not None:
            values.append(target_val)
    return values


def _make_event(machine_code, machine_type, ts_external_id, ts_label, pattern, start_ms, end_ms,
                 asset_id, description, extra_metadata):
    ext_id = f"anomaly_{machine_code}_{ts_external_id}_{pattern}_{start_ms}"
    metadata = {
        "machine_code": machine_code.upper(),
        "machine_type": machine_type,
        "timeseries": ts_external_id,
        "timeseries_label": ts_label,
        "pattern": pattern,
        "description": description,
    }
    metadata.update({k: str(v) for k, v in extra_metadata.items()})
    return EventWrite(
        external_id=ext_id,
        data_set_id=DATA_SET_ID,
        type="Data Quality Alert",
        subtype=pattern,
        start_time=start_ms,
        end_time=end_ms,
        description=description,
        asset_ids=[asset_id] if asset_id else None,
        metadata=metadata,
    )


def detect_anomalies_for_machine(client, cfg: dict, asset_id, start_ms: int, end_ms: int) -> list:
    machine_code = cfg["code"]
    machine_type = cfg["machine_type"]
    primary_field = PRIMARY_FIELD[machine_type]
    events = []

    # One history fetch per machine, reused across all of its watched
    # timeseries below (patterns 3 & 4 never touch raw datapoints).
    current_event, baseline_events = _production_report_history(client, machine_type, machine_code, start_ms, end_ms)
    current_shift = _shift_of(current_event)

    for ts_key, pr_field, ts_label, direction in WATCHED_TIMESERIES[machine_type]:
        ts_external_id = cfg.get(ts_key)
        if not ts_external_id:
            continue

        # Patterns 1 & 2: fresh raw-datapoint scan of this hour.
        for pattern, ts_ms, prev_val, curr_val in _scan_for_reset_and_noise(client, ts_external_id, start_ms, end_ms):
            if pattern == "RESET_TO_ZERO":
                desc = f"{machine_code.upper()} / {ts_label}: contador reiniciado a cero ({prev_val:,.0f} -> {curr_val:,.0f})."
            else:
                desc = (f"{machine_code.upper()} / {ts_label}: el contador bajo sin llegar a cero "
                        f"({prev_val:,.0f} -> {curr_val:,.0f}) -- posible ruido de sensor, no un reinicio real.")
            events.append(_make_event(
                machine_code, machine_type, ts_external_id, ts_label, pattern, ts_ms, ts_ms, asset_id, desc,
                {"value_before": prev_val, "value_after": curr_val},
            ))

        # Pattern 3: this hour's value vs. the highest value seen in the
        # trailing week for this metric (any shift, idle hours included --
        # a max is unaffected by low/zero values pulling an average down).
        current_value = _extract_metric(current_event, pr_field)
        all_baseline_values = [v for e in baseline_events if (v := _extract_metric(e, pr_field)) is not None]

        if current_value is not None and all_baseline_values:
            baseline_max = max(all_baseline_values)
            if current_value > baseline_max:
                desc = (f"{machine_code.upper()} / {ts_label}: nuevo maximo de la ultima semana "
                        f"({current_value:,.0f}, anterior maximo {baseline_max:,.0f}).")
                events.append(_make_event(
                    machine_code, machine_type, ts_external_id, ts_label, "NEW_WEEKLY_MAX", start_ms, end_ms, asset_id, desc,
                    {"current_value": current_value, "baseline_max": baseline_max, "baseline_days": BASELINE_WINDOW_DAYS},
                ))

        # Pattern 4: this hour's speed vs. the machine's normal per-shift
        # running speed, learned only from hours it was actually active --
        # direction depends on whether this metric is production (less is
        # bad) or scrap/waste (more is bad).
        active_values = _active_same_shift_baseline(baseline_events, current_shift, primary_field, pr_field)

        if current_value is not None and active_values:
            # Median, not mean: a single leftover pre-fix outlier in the
            # trailing week (e.g. a historical reset-bug artifact never
            # backfilled) would otherwise skew every future comparison.
            baseline_avg = statistics.median(active_values)

            # current_value > 0 matters here: a fully stopped machine isn't
            # "running slower than usual", it's just not running -- a
            # different situation this pattern isn't meant to catch.
            if (direction == PRODUCTION and current_value > 0 and baseline_avg > 0
                    and current_value < baseline_avg * SLOW_RUNNING_RATIO):
                desc = (f"{machine_code.upper()} / {ts_label}: operando mas lento de lo usual para el turno "
                        f"{current_shift} ({current_value:,.0f} vs. mediana {baseline_avg:,.0f}).")
                events.append(_make_event(
                    machine_code, machine_type, ts_external_id, ts_label, "SLOW_RUNNING", start_ms, end_ms, asset_id, desc,
                    {"current_value": current_value, "baseline_avg": round(baseline_avg, 1),
                     "shift": current_shift, "baseline_days": BASELINE_WINDOW_DAYS, "training_samples": len(active_values)},
                ))

            if direction == SCRAP and baseline_avg > 0 and current_value >= baseline_avg * EXCESS_SCRAP_RATIO:
                desc = (f"{machine_code.upper()} / {ts_label}: mas alto de lo usual para el turno "
                        f"{current_shift} ({current_value:,.0f} vs. mediana {baseline_avg:,.0f}).")
                events.append(_make_event(
                    machine_code, machine_type, ts_external_id, ts_label, "EXCESS_SCRAP", start_ms, end_ms, asset_id, desc,
                    {"current_value": current_value, "baseline_avg": round(baseline_avg, 1),
                     "shift": current_shift, "baseline_days": BASELINE_WINDOW_DAYS, "training_samples": len(active_values)},
                ))

    return events


def detect_all_anomalies(client, data: dict) -> dict:
    hours_ago = int(data.get("hours_ago", 1))
    dry_run = bool(data.get("dry_run", False))
    machine_codes = data.get("machine_codes")

    start_ms, end_ms, hour_start_local = _hour_window(hours_ago)

    configs = MACHINE_CONFIGS
    if machine_codes:
        wanted = {c.lower() for c in machine_codes}
        configs = [c for c in configs if c["code"] in wanted]

    asset_ids_by_ext_id = _resolve_asset_ids(client, configs)

    all_events = []
    per_machine = {}
    for cfg in configs:
        asset_id = asset_ids_by_ext_id.get(cfg["asset_ext_id"])
        machine_events = detect_anomalies_for_machine(client, cfg, asset_id, start_ms, end_ms)
        all_events.extend(machine_events)
        per_machine[cfg["code"]] = len(machine_events)

    summary_by_pattern = {}
    for e in all_events:
        summary_by_pattern[e.subtype] = summary_by_pattern.get(e.subtype, 0) + 1

    if dry_run:
        written = 0
    else:
        if all_events:
            client.events.upsert(all_events)
        written = len(all_events)

    return {
        "window": {
            "start_local": hour_start_local.strftime("%Y-%m-%d %H:%M"),
            "timezone": "GMT-4",
        },
        "dry_run": dry_run,
        "total_anomalies": len(all_events),
        "written": written,
        "by_pattern": summary_by_pattern,
        "by_machine": {k: v for k, v in per_machine.items() if v > 0},
        "anomalies": [
            {"external_id": e.external_id, "subtype": e.subtype, "description": e.description}
            for e in all_events
        ] if dry_run else None,
    }


def handle(client: "CogniteClient" = None, data: dict = None) -> dict:  # noqa: F821 - injected by CDF at runtime
    """
    Cognite Function entry point. `data` accepts:
      - hours_ago (int, default 1): which hour to analyze.
      - machine_codes (list[str], optional): restrict to specific machines.
      - dry_run (bool, default False): detect and return, write nothing.
    """
    return detect_all_anomalies(client, data or {})
