"""
Hourly production report -- Cognite Function.

Ported from notebooks/Notebooks_dataset_220726_113831_CreateHourlyReport.ipynb.
Same KPI logic as the notebook; changes made while porting are noted inline
and summarized here:

1. Asset IDs are resolved ONCE per invocation via a single batched
   `assets.retrieve_multiple()` call, instead of one `assets.retrieve()` (or
   worse, a fuzzy `assets.search()`) per machine inside the loop. The
   mapping never changes hour to hour, so the notebook was spending up to
   ~25 API calls every single run resolving something static.
2. The fuzzy-search fallback (used only when a machine's asset_ext_id truly
   isn't found) now returns a warning describing exactly what it matched,
   surfaced both in the function's return value and in stdout. Previously
   it silently trusted the first search hit with no record of it happening
   -- a wrong match would attach a whole hour of production data to the
   wrong physical machine with nothing to flag it.
3. The identical shift/date/slot/hour-label calculation that was
   copy-pasted into all five generate_*_event functions is now one shared
   helper, _shift_context().
4. Each generate_*_event function returns a small result dict instead of
   only printing, and the orchestrator aggregates a structured summary
   (counts of ok/skipped/error, plus per-machine detail) as the function's
   JSON return value -- visible in Fusion's function call history, not just
   in logs someone has to go looking for.
5. `data` now optionally accepts `hours_ago` (int, default 1 -- reproduces
   the original "most recently completed hour" behavior) and
   `machine_codes` (list[str], to restrict a run to specific machines).
   This gives you a manual backfill/retry path for a specific hour or
   machine without waiting for the next schedule -- the notebook had no
   such mechanism, so a transient failure meant that hour's data for that
   machine was just gone.
6. `data` also accepts `dry_run` (bool, default False). All the reads
   (asset resolution, time series counters) still hit real CDF -- there's
   no local copy of this data to test against -- but the final
   `client.events.upsert()` is skipped, and the would-be event payload is
   returned instead. This is what local_test.py uses by default, so running
   it against your real CDF project doesn't write or overwrite anything
   until you deliberately turn dry_run off.
7. `calculate_hourly_counter_delta()`'s reset handling (not from the
   notebook's original design, but a bug found after this ran live for a
   while) used to add a downward step's absolute post-step value into the
   hourly delta whenever it saw ANY decrease, on the assumption that any
   decrease meant "the counter reset to 0, so the new reading IS the
   increment since reset." On a large cumulative counter, a downward step
   that's just noise (not an actual reset) doesn't land near 0 -- so this
   injected the counter's entire multi-million absolute value into a
   single hour, observed live on MINSTER_L1. Now only a step landing at/
   near 0 (see `_RESET_TO_ZERO_EPS`) counts as a real reset; any other
   downward step is logged and excluded from the delta as noise.

Deployment and scheduling: see README.md in this folder.
"""
from datetime import datetime, timedelta
from cognite.client.data_classes import EventWrite
from cognite.client.exceptions import CogniteNotFoundError

from config import (
    CAN_WEIGHT_KG,
    CANS_PER_SHORT_CAN,
    CANS_PER_TRIMMER_JAM,
    DATA_SET_ID,
    DOWNTIME_PER_SHORT_CAN_MIN,
    DOWNTIME_PER_TRIM_JAM_MIN,
    HOUR_INTERVAL_MAP,
    LOCAL_TZ,
    MACHINE_CONFIGS,
)


def _shift_context(last_hour_start_local: datetime) -> dict:
    """
    Shift/date/slot/hour-label calculation shared by every generate_*_event
    function (previously duplicated identically five times in the notebook).
    """
    start_hour_local = last_hour_start_local.hour

    # Day: 06:00-18:00 | Night: 18:00-06:00
    shift_code = "day" if 6 <= start_hour_local < 18 else "night"
    shift_start_hour = 6 if shift_code == "day" else 18

    # Overnight hours (00:00-05:59) belong to the shift that started the
    # previous calendar day.
    shift_date = (
        last_hour_start_local - timedelta(days=1)
        if start_hour_local < 6
        else last_hour_start_local
    )
    date_str = shift_date.strftime("%Y%m%d")

    hour_index = ((start_hour_local - shift_start_hour) % 24) + 1
    entry_slot = f"{hour_index:02d}"

    hour_interval = HOUR_INTERVAL_MAP.get(
        start_hour_local,
        f"{start_hour_local} a {(start_hour_local + 1) % 24}",
    )

    return {
        "shift_code": shift_code,
        "date_str": date_str,
        "entry_slot": entry_slot,
        "hour_interval": hour_interval,
    }


def _resolve_asset_ids(client, ext_ids: list) -> tuple:
    """
    Resolves CDF asset IDs for a list of external_ids in ONE batched call.

    Returns (id_by_ext_id, warnings). Any external_id not found by exact
    lookup falls back to a fuzzy name search -- inherently risky, since it
    can match a similarly-named but wrong asset -- so every time it fires, a
    warning describing exactly what was matched is recorded instead of
    silently trusting the first hit.
    """
    id_by_ext_id = {}
    warnings = []

    found = client.assets.retrieve_multiple(external_ids=ext_ids, ignore_unknown_ids=True)
    for asset in found:
        id_by_ext_id[asset.external_id] = asset.id

    missing = [e for e in ext_ids if e not in id_by_ext_id]
    for ext_id in missing:
        res = client.assets.search(query=ext_id, limit=5)
        if res:
            match = res[0]
            id_by_ext_id[ext_id] = match.id
            warnings.append(
                f"Asset '{ext_id}' not found by external_id -- fell back to search and "
                f"matched '{match.name}' (external_id={match.external_id}, id={match.id}). "
                "Verify this is the correct asset."
            )
        else:
            warnings.append(f"Could not resolve asset '{ext_id}' by external_id or search.")

    return id_by_ext_id, warnings


_RESET_TO_ZERO_EPS = 1.0  # a genuine counter reset lands at/near 0, not just "lower than before"


def calculate_hourly_counter_delta(client, external_id: str, start_ms: int, end_ms: int):
    """
    Calculates step-by-step counter accumulation and handles mid-hour resets.
    """
    try:
        dps = client.time_series.data.retrieve(
            external_id=external_id,
            start=start_ms,
            end=end_ms,
            limit=None,
            ignore_unknown_ids=True,
        )

        if not dps or len(dps) == 0:
            print(f"  [Warning] [{external_id}] No datapoints found in window.")
            return 0.0, False

        def safe_float(val) -> float:
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        first_value = safe_float(dps[0].value)
        last_value = safe_float(dps[-1].value)

        if len(dps) == 1:
            print(f"  [{external_id}] First: {first_value:,.1f} | Last: {last_value:,.1f} | Delta: 0.0 | Reset: False")
            return 0.0, False

        hourly_delta = 0.0
        reset_occurred = False

        for i in range(1, len(dps)):
            prev_val = safe_float(dps[i - 1].value)
            curr_val = safe_float(dps[i].value)
            step_diff = curr_val - prev_val

            if step_diff < 0:
                if curr_val < _RESET_TO_ZERO_EPS:
                    # Counter genuinely reset (rolled back to ~0) -- curr_val IS the
                    # increment since the reset.
                    reset_occurred = True
                    hourly_delta += curr_val
                else:
                    # Downward step that didn't land near 0 isn't a real reset -- on a
                    # large cumulative counter (e.g. millions of lifetime strokes) this
                    # is sensor/telemetry noise. Treating curr_val as the delta here
                    # previously injected the counter's entire absolute value into a
                    # single hour (seen live: an 11M-count blip read as one hour of
                    # MINSTER production). Exclude it instead.
                    print(f"  [Warning] [{external_id}] Downward step not at 0 (prev={prev_val:,.1f} -> curr={curr_val:,.1f}); treating as noise, excluded from delta.")
            else:
                hourly_delta += step_diff

        print(f"  [{external_id}] First: {first_value:,.1f} | Last: {last_value:,.1f} | Delta: {hourly_delta:,.1f} | Reset: {reset_occurred}")
        return hourly_delta, reset_occurred

    except CogniteNotFoundError:
        # Belt-and-suspenders: ignore_unknown_ids=True above should already
        # prevent this from firing for a missing time series.
        print(f"  [Warning] TimeSeries '{external_id}' not found.")
        return 0.0, False
    except Exception as e:
        print(f"  [Error] Reading '{external_id}': {e}")
        return 0.0, False


def _finalize_event(client, event: EventWrite, dry_run: bool, label: str) -> dict:
    """
    Either upserts `event` to CDF, or (dry_run=True) skips the write
    entirely and returns what WOULD have been written -- lets you validate
    the KPI math against real, live CDF data (real time series reads) without
    creating or overwriting any real event. Safe to run against production.
    """
    machine_code = event.metadata.get("machine_code") or event.metadata.get("printer_code")

    if dry_run:
        print(f"  --> [DRY RUN] Would upsert {label} Event: '{event.external_id}' (nothing written)")
        print(f"      metadata: {event.metadata}")
        return {
            "code": machine_code,
            "status": "dry_run",
            "external_id": event.external_id,
            "metadata": event.metadata,
        }

    res = client.events.upsert(event)
    ext_id = res.external_id if hasattr(res, "external_id") else res[0].external_id
    cdf_id = res.id if hasattr(res, "id") else res[0].id
    print(f"  --> Successfully posted {label} Event: '{ext_id}' (CDF ID: {cdf_id})")
    return {"code": machine_code, "status": "ok", "external_id": ext_id, "id": cdf_id}


def generate_printer_event(client, cfg: dict, start_ms: int, end_ms: int, last_hour_start_local: datetime, asset_id: int, dry_run: bool = False) -> dict:
    ctx = _shift_context(last_hour_start_local)
    printer_code = cfg["code"]
    nominal_cap = cfg.get("nominal_capacity", 0.0)

    hourly_production, prod_reset = calculate_hourly_counter_delta(client, cfg["ts_prod"], start_ms, end_ms)
    hourly_retrac, retrac_reset = calculate_hourly_counter_delta(client, cfg["ts_retract"], start_ms, end_ms)
    blow_off, blowoff_reset = calculate_hourly_counter_delta(client, cfg["ts_blow_off"], start_ms, end_ms)

    if nominal_cap > 0:
        downtime_minutes = max(0.0, round(60.0 - ((hourly_production * 60.0) / nominal_cap), 2))
        efficiency = round((hourly_production * 100.0) / nominal_cap, 2)
    else:
        downtime_minutes = 60.0
        efficiency = 0.0

    event_ext_id = f"report_{printer_code}_{ctx['date_str']}_{ctx['shift_code']}_entry_{ctx['entry_slot']}"

    resets = [name for name, flag in (("prod", prod_reset), ("retrac", retrac_reset), ("blow_off", blowoff_reset)) if flag]
    obs_text = f"Resets detected: {', '.join(resets)}" if resets else "Operación estándar"

    report_event = EventWrite(
        external_id=event_ext_id,
        data_set_id=DATA_SET_ID,
        type="Production Report",
        subtype="Hourly Entry",
        start_time=start_ms,
        end_time=end_ms,
        description=f"Production Report {ctx['hour_interval']} for Printer {printer_code.upper()}",
        asset_ids=[asset_id],
        metadata={
            "timezone": "GMT-4",
            "printer_code": printer_code,
            "shift": ctx["shift_code"],
            "hour_interval": ctx["hour_interval"],
            "hourly_production": str(hourly_production),
            "hourly_retrac": str(hourly_retrac),
            "blow_off": str(blow_off),
            "downtime_minutes": str(downtime_minutes),
            "efficiency": f"{efficiency:.2f}%",
            "observations": obs_text,
        },
    )

    return _finalize_event(client, report_event, dry_run, label="Printer")


def generate_di_event(client, cfg: dict, start_ms: int, end_ms: int, last_hour_start_local: datetime, asset_id: int, dry_run: bool = False) -> dict:
    ctx = _shift_context(last_hour_start_local)
    machine_code = cfg["code"]

    prod_count, prod_reset = calculate_hourly_counter_delta(client, cfg["ts_prod"], start_ms, end_ms)
    short_count, short_reset = calculate_hourly_counter_delta(client, cfg["ts_short_cans"], start_ms, end_ms)
    trim_count, trim_reset = calculate_hourly_counter_delta(client, cfg["ts_trimmer_jams"], start_ms, end_ms)

    cans_from_short = short_count * CANS_PER_SHORT_CAN
    cans_from_trim = trim_count * CANS_PER_TRIMMER_JAM

    downtime_short = short_count * DOWNTIME_PER_SHORT_CAN_MIN
    downtime_trim = trim_count * DOWNTIME_PER_TRIM_JAM_MIN
    total_downtime_min = min(60.0, downtime_short + downtime_trim)

    total_scrap_cans = cans_from_short + cans_from_trim
    merma_kg = round(total_scrap_cans * CAN_WEIGHT_KG, 2)

    total_produced_and_lost = prod_count + total_scrap_cans
    pct_merma = (
        round((total_scrap_cans / total_produced_and_lost * 100.0), 2)
        if total_produced_and_lost > 0
        else 0.0
    )
    pct_eficiencia = round(((60.0 - total_downtime_min) / 60.0 * 100.0), 2)

    resets = [name for name, flag in (("prod", prod_reset), ("short_cans", short_reset), ("trimmer_jams", trim_reset)) if flag]

    obs_parts = []
    if total_downtime_min == 0:
        obs_parts.append("Operación normal")
    elif short_count > 0 and trim_count > 0:
        obs_parts.append("Parada por latas cortas y trancamiento")
    elif short_count > 0:
        obs_parts.append("Parada por latas cortas")
    else:
        obs_parts.append("Parada por trancamiento trimmer")
    if resets:
        obs_parts.append(f"(Resets: {', '.join(resets)})")
    obs_text = " ".join(obs_parts)

    event_ext_id = f"report_{machine_code}_{ctx['date_str']}_{ctx['shift_code']}_entry_{ctx['entry_slot']}"

    report_event = EventWrite(
        external_id=event_ext_id,
        data_set_id=DATA_SET_ID,
        type="Production Report",
        subtype="Hourly Entry DI",
        start_time=start_ms,
        end_time=end_ms,
        description=f"Production Report {ctx['hour_interval']} for D&I Machine {machine_code.upper()}",
        asset_ids=[asset_id],
        metadata={
            "timezone": "GMT-4",
            "machine_code": machine_code.upper(),
            "shift": ctx["shift_code"],
            "hour_interval": ctx["hour_interval"],
            "hourly_production": str(int(prod_count)),
            "short_cans_per_hour": str(int(short_count)),
            "trimmer_jams_per_hour": str(int(trim_count)),
            "cans_by_short_can": str(int(cans_from_short)),
            "cans_by_trimmer_jam": str(int(cans_from_trim)),
            "downtime_by_short_can_min": f"{downtime_short:.2f}",
            "downtime_by_trimmer_jam_min": f"{downtime_trim:.2f}",
            "total_downtime_min": f"{total_downtime_min:.2f}",
            "merma_kg": f"{merma_kg:.2f}",
            "pct_merma": f"{pct_merma:.2f}%",
            "pct_eficiencia": f"{pct_eficiencia:.2f}%",
            "observations": obs_text,
        },
    )

    return _finalize_event(client, report_event, dry_run, label="D&I")


def generate_standum_event(client, cfg: dict, start_ms: int, end_ms: int, last_hour_start_local: datetime, asset_id: int, dry_run: bool = False) -> dict:
    ctx = _shift_context(last_hour_start_local)
    machine_code = cfg["code"]

    hourly_production, prod_reset = calculate_hourly_counter_delta(client, cfg["ts_prod"], start_ms, end_ms)
    short_count, short_reset = calculate_hourly_counter_delta(client, cfg["ts_short_cans"], start_ms, end_ms)
    trim_count, trim_reset = calculate_hourly_counter_delta(client, cfg["ts_trimmer_jams"], start_ms, end_ms)

    cans_from_short = short_count * CANS_PER_SHORT_CAN
    cans_from_trim = trim_count * CANS_PER_TRIMMER_JAM

    downtime_short = short_count * DOWNTIME_PER_SHORT_CAN_MIN
    downtime_trim = trim_count * DOWNTIME_PER_TRIM_JAM_MIN
    total_downtime_min = min(60.0, downtime_short + downtime_trim)

    total_scrap_cans = cans_from_short + cans_from_trim
    merma_kg = round(total_scrap_cans * CAN_WEIGHT_KG, 2)

    total_produced_and_lost = hourly_production + total_scrap_cans
    pct_merma = (
        round((total_scrap_cans / total_produced_and_lost * 100.0), 2)
        if total_produced_and_lost > 0
        else 0.0
    )
    pct_eficiencia = round(((60.0 - total_downtime_min) / 60.0 * 100.0), 2)

    resets = [name for name, flag in (("prod", prod_reset), ("short_cans", short_reset), ("trimmer_jams", trim_reset)) if flag]

    obs_parts = []
    if total_downtime_min == 0:
        obs_parts.append("Operación normal")
    elif short_count > 0 and trim_count > 0:
        obs_parts.append("Parada por latas cortas y trancamiento")
    elif short_count > 0:
        obs_parts.append("Parada por latas cortas")
    else:
        obs_parts.append("Parada por trancamiento trimmer")
    if resets:
        obs_parts.append(f"(Resets: {', '.join(resets)})")
    obs_text = " ".join(obs_parts)

    event_ext_id = f"report_{machine_code}_{ctx['date_str']}_{ctx['shift_code']}_entry_{ctx['entry_slot']}"

    report_event = EventWrite(
        external_id=event_ext_id,
        data_set_id=DATA_SET_ID,
        type="Production Report",
        subtype="Hourly Entry Standum",
        start_time=start_ms,
        end_time=end_ms,
        description=f"Production Report {ctx['hour_interval']} for Standum {machine_code.upper()}",
        asset_ids=[asset_id],
        metadata={
            "timezone": "GMT-4",
            "machine_code": machine_code.upper(),
            "shift": ctx["shift_code"],
            "hour_interval": ctx["hour_interval"],
            "hourly_production": str(int(hourly_production)),
            "short_cans_per_hour": str(int(short_count)),
            "trimmer_jams_per_hour": str(int(trim_count)),
            "cans_by_short_can": str(int(cans_from_short)),
            "cans_by_trimmer_jam": str(int(cans_from_trim)),
            "downtime_by_short_can_min": f"{downtime_short:.2f}",
            "downtime_by_trimmer_jam_min": f"{downtime_trim:.2f}",
            "total_downtime_min": f"{total_downtime_min:.2f}",
            "merma_kg": f"{merma_kg:.2f}",
            "pct_merma": f"{pct_merma:.2f}%",
            "pct_eficiencia": f"{pct_eficiencia:.2f}%",
            "observations": obs_text,
        },
    )

    return _finalize_event(client, report_event, dry_run, label="Standum")


def generate_minster_event(client, cfg: dict, start_ms: int, end_ms: int, last_hour_start_local: datetime, asset_id: int, dry_run: bool = False) -> dict:
    """
    Tracks Coil Strokes (Golpes Bobina) and Shift Strokes (Golpes Turno).
    Efficiency is based on hourly coil strokes without scrap/mermas.
    """
    ctx = _shift_context(last_hour_start_local)
    machine_code = cfg["code"]
    nominal_cap = cfg.get("nominal_capacity", 120000.0)

    golpes_bob, bob_reset = calculate_hourly_counter_delta(client, cfg["ts_golpes_bob"], start_ms, end_ms)
    golpes_turno, turno_reset = calculate_hourly_counter_delta(client, cfg["ts_golpes_turno"], start_ms, end_ms)

    hourly_production = golpes_bob

    efficiency = round((hourly_production * 100.0) / nominal_cap, 2) if nominal_cap > 0 else 0.0
    downtime_minutes = (
        max(0.0, round(60.0 - ((hourly_production * 60.0) / nominal_cap), 2))
        if nominal_cap > 0
        else 0.0
    )

    resets = [name for name, flag in (("golpes_bobina", bob_reset), ("golpes_turno", turno_reset)) if flag]
    obs_text = f"Resets detectados: {', '.join(resets)}" if resets else "Operación normal"

    event_ext_id = f"report_{machine_code}_{ctx['date_str']}_{ctx['shift_code']}_entry_{ctx['entry_slot']}"

    report_event = EventWrite(
        external_id=event_ext_id,
        data_set_id=DATA_SET_ID,
        type="Production Report",
        subtype="Hourly Entry MINSTER",
        start_time=start_ms,
        end_time=end_ms,
        description=f"Production Report {ctx['hour_interval']} for MINSTER {machine_code.upper()}",
        asset_ids=[asset_id],
        metadata={
            "timezone": "GMT-4",
            "machine_code": machine_code.upper(),
            "shift": ctx["shift_code"],
            "hour_interval": ctx["hour_interval"],
            "golpes_bobina_hora": str(int(golpes_bob)),
            "golpes_turno_hora": str(int(golpes_turno)),
            "hourly_production": str(int(hourly_production)),
            "pct_eficiencia": f"{efficiency:.2f}%",
            "downtime_minutes": f"{downtime_minutes:.2f}",
            "observations": obs_text,
        },
    )

    return _finalize_event(client, report_event, dry_run, label="MINSTER")


def generate_ispray_event(client, cfg: dict, start_ms: int, end_ms: int, last_hour_start_local: datetime, asset_id: int, dry_run: bool = False) -> dict:
    """
    Production and efficiency only (no scrap/mermas tracked for ISPRAY).
    """
    ctx = _shift_context(last_hour_start_local)
    machine_code = cfg["code"]
    nominal_cap = cfg.get("nominal_capacity", 30000.0)

    hourly_production, prod_reset = calculate_hourly_counter_delta(client, cfg["ts_prod"], start_ms, end_ms)

    efficiency = round((hourly_production * 100.0) / nominal_cap, 2) if nominal_cap > 0 else 0.0
    downtime_minutes = (
        max(0.0, round(60.0 - ((hourly_production * 60.0) / nominal_cap), 2))
        if nominal_cap > 0
        else 0.0
    )

    obs_text = "Reset detectado en contador" if prod_reset else "Operación normal"
    event_ext_id = f"report_{machine_code}_{ctx['date_str']}_{ctx['shift_code']}_entry_{ctx['entry_slot']}"

    report_event = EventWrite(
        external_id=event_ext_id,
        data_set_id=DATA_SET_ID,
        type="Production Report",
        subtype="Hourly Entry ISPRAY",
        start_time=start_ms,
        end_time=end_ms,
        description=f"Production Report {ctx['hour_interval']} for ISPRAY {machine_code.upper()}",
        asset_ids=[asset_id],
        metadata={
            "timezone": "GMT-4",
            "machine_code": machine_code.upper(),
            "shift": ctx["shift_code"],
            "hour_interval": ctx["hour_interval"],
            "hourly_production": str(int(hourly_production)),
            "pct_eficiencia": f"{efficiency:.2f}%",
            "downtime_minutes": f"{downtime_minutes:.2f}",
            "observations": obs_text,
        },
    )

    return _finalize_event(client, report_event, dry_run, label="ISPRAY")


_GENERATORS = {
    "printer": generate_printer_event,
    "standum": generate_standum_event,
    "di": generate_di_event,
    "minster": generate_minster_event,
    "ispray": generate_ispray_event,
}


def run_all_production_reports(client, data: dict = None) -> dict:
    data = data or {}

    # hours_ago=1 (default) reproduces the notebook's original behavior:
    # process the most recently completed hour. hours_ago=2 re-processes
    # the hour before that, etc. -- use this for manual backfill of a
    # specific missed/failed hour.
    hours_ago = int(data.get("hours_ago", 1))

    # Optional: restrict this run to specific machine codes (as in
    # MACHINE_CONFIGS's "code" field, case-insensitive) instead of all of
    # them -- useful for testing or re-running a single machine.
    only_codes = data.get("machine_codes")

    # Optional: compute everything (real reads from CDF time series/assets)
    # but skip the final client.events.upsert() call -- lets you validate
    # the KPI math against live data without writing/overwriting anything.
    dry_run = bool(data.get("dry_run", False))

    now_local = datetime.now(LOCAL_TZ)
    last_hour_end_local = now_local.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_ago - 1)
    last_hour_start_local = last_hour_end_local - timedelta(hours=1)

    start_ms = int(last_hour_start_local.timestamp() * 1000)
    end_ms = int(last_hour_end_local.timestamp() * 1000)

    configs = MACHINE_CONFIGS
    if only_codes:
        wanted = {c.lower() for c in only_codes}
        configs = [c for c in configs if c["code"].lower() in wanted]

    print("=" * 80)
    print(f"EXECUTION WINDOW (GMT-4): {last_hour_start_local.strftime('%Y-%m-%d %H:%M')} to {last_hour_end_local.strftime('%H:%M')}")
    print("=" * 80)

    id_by_ext_id, asset_warnings = _resolve_asset_ids(client, [c["asset_ext_id"] for c in configs])
    for w in asset_warnings:
        print(f"  [Warning] {w}")

    results = []
    for cfg in configs:
        m_code = cfg["code"].upper()
        m_type_clean = cfg.get("machine_type", "").lower().strip()
        print(f"\n--- Processing [{m_type_clean.upper()}]: {m_code} ({cfg['asset_ext_id']}) ---")

        generator = _GENERATORS.get(m_type_clean)
        if generator is None:
            msg = f"Unsupported machine type: '{cfg.get('machine_type')}'"
            print(f"  [Warning] {msg}")
            results.append({"code": cfg["code"], "status": "skipped", "reason": msg})
            continue

        asset_id = id_by_ext_id.get(cfg["asset_ext_id"])
        if asset_id is None:
            msg = f"Could not resolve asset '{cfg['asset_ext_id']}'"
            print(f"  [Error] {msg}. Skipping {m_code}...")
            results.append({"code": cfg["code"], "status": "error", "reason": msg})
            continue

        try:
            results.append(generator(client, cfg, start_ms, end_ms, last_hour_start_local, asset_id, dry_run=dry_run))
        except Exception as err:
            print(f"  [Error] Unexpected exception for {m_code}: {err}. Skipping...")
            results.append({"code": cfg["code"], "status": "error", "reason": str(err)})

    summary = {
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "dry_run": sum(1 for r in results if r.get("status") == "dry_run"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
    }

    return {
        "window": {
            "start_local": last_hour_start_local.strftime("%Y-%m-%d %H:%M"),
            "end_local": last_hour_end_local.strftime("%Y-%m-%d %H:%M"),
            "timezone": "GMT-4",
        },
        "summary": summary,
        "results": results,
        "asset_resolution_warnings": asset_warnings,
    }


def handle(client: "CogniteClient" = None, data: dict = None) -> dict:  # noqa: F821 - injected by CDF at runtime
    """
    Cognite Function entry point. See run_all_production_reports() for what
    `data` accepts (hours_ago, machine_codes, dry_run).
    """
    return run_all_production_reports(client, data)
