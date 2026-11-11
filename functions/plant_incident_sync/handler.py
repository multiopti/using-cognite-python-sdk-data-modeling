"""
plant_incident_sync -- writes the hourly incidents operators report at the plant to CDF.

Path: plant Reporte de Producción -> Node-RED -> Optix matrices Model/OBSERVACIONES/<key>_OBS_DATA_WEEK -> Optix
NetLogic IncidentSnapshot (JSON of the cells with an incident) -> MQTTPublisherIncidents -> AWS IoT Core, topic
SuperenvasesIncidents/snapshot -> CDF hosted extractor job -> RAW db_superenvases_raw.raw_incident_snapshots ->
THIS function (scheduled every 5 minutes) -> the hourly `Production Report` events written by
hourly_production_report.

Snapshot (the Value of the INCIDENTS_SNAPSHOT record):
    {"v":1,"sent_at":"2026-11-10T21:18:54-04:00","cells":{"STANDUM32":[[102,0],[103,4]], ...}}
cell index = weekday * 24 + hour (Sunday = 0), on the Optix clock; sent_at is that clock, so each cell's date is
the most recent such weekday/hour before sent_at. A machine missing from "cells" has no incidents.

Rules (agreed 2026-11-09/10):
  - Incidents are only REPORTED, never cleared: every code >= 0 (0 = "Operación estándar" too) is written; a changed
    code overwrites the old one. Hours with nothing reported are never touched, so older Fusion observations stay.
  - The plant is the only place incidents are edited (Fusion editing is disabled when this ships).
  - Written to the event's metadata (added, the rest of the event is untouched): observations / observaciones (the
    text Fusion shows), incident_code, incident_source="plant", incident_synced_at.
  - An event is only updated when its observations text or incident_code differ, so re-runs write nothing, and when
    hourly_production_report re-runs an hour and puts its automatic text back, the next run restores the incident.
  - If the hour's event doesn't exist yet (hourly_production_report hasn't run for it), the cell waits for a later
    run; no half-empty events are created.
  - Today's cell for the current hour (unfinished) and later hours (the column the weekly wipe has just cleared, or
    is about to) are ignored.
  - No snapshot newer than MAX_AGE_MINUTES (plant offline): nothing is done.

`data` (all optional):
    dry_run          bool, default False: compute everything, write nothing; the result lists what WOULD change.
    machines         list of machine codes (e.g. ["di11"]) to limit the run to.
    snapshot         a snapshot (dict or JSON string) to use instead of reading RAW -- for tests.
    max_age_minutes  override MAX_AGE_MINUTES.
"""
import json
from datetime import datetime, timedelta, timezone

from cognite.client.data_classes import EventUpdate
from cognite.client.exceptions import CogniteAPIError

from config import (
    EVENT_TYPE,
    INCIDENTES_OPCIONES,
    MAX_AGE_MINUTES,
    OBS_KEY_TO_CODE,
    RAW_DB,
    RAW_TABLE,
    SNAPSHOT_TAG,
)


def parse_snapshot(value):
    snap = json.loads(value) if isinstance(value, str) else dict(value)
    if snap.get("v") != 1 or "sent_at" not in snap or not isinstance(snap.get("cells"), dict):
        raise ValueError(f"unexpected snapshot format: {str(value)[:200]}")
    snap["sent_at_dt"] = datetime.fromisoformat(snap["sent_at"])
    if snap["sent_at_dt"].tzinfo is None:
        raise ValueError(f"sent_at has no UTC offset: {snap['sent_at']}")
    return snap


def latest_snapshot(client, max_age_minutes):
    """Newest INCIDENTS_SNAPSHOT stored in RAW in the last max_age_minutes, or None."""
    since_ms = int((datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).timestamp() * 1000)
    best = None
    for row in client.raw.rows.list(RAW_DB, RAW_TABLE, min_last_updated_time=since_ms, limit=None):
        for rec in (row.columns or {}).get("records") or []:
            if isinstance(rec, dict) and rec.get("TagName") == SNAPSHOT_TAG:
                snap = parse_snapshot(rec.get("Value"))
                snap["raw_key"] = row.key
                if best is None or snap["sent_at_dt"] > best["sent_at_dt"]:
                    best = snap
    return best


def hour_context(hour_start):
    """Same shift/date/slot rules as hourly_production_report._shift_context()."""
    h = hour_start.hour
    shift_code = "day" if 6 <= h < 18 else "night"
    shift_start = 6 if shift_code == "day" else 18
    shift_date = hour_start - timedelta(days=1) if h < 6 else hour_start
    return shift_code, shift_date.strftime("%Y%m%d"), ((h - shift_start) % 24) + 1


def cells_to_targets(snap, machines=None):
    """(targets, skipped): one target per reported cell -> its event external_id and the text to write."""
    now = snap["sent_at_dt"].replace(tzinfo=None)              # Optix wall clock, the matrices' clock
    today_wd = (now.weekday() + 1) % 7                           # Sunday = 0
    this_hour = now.replace(minute=0, second=0, microsecond=0)
    wanted = {m.lower() for m in machines} if machines else None
    targets, skipped = [], []
    for key, cells in snap["cells"].items():
        code = OBS_KEY_TO_CODE.get(key)
        if code is None:
            skipped.append({"machine": key, "reason": "unknown machine key"})
            continue
        if wanted is not None and code not in wanted:
            continue
        for cell, incident in cells:
            cell, incident = int(cell), int(incident)
            d, h = divmod(cell, 24)
            if not (0 <= d < 7 and incident >= 0):
                skipped.append({"machine": key, "cell": cell, "code": incident, "reason": "invalid cell"})
                continue
            days_back = (today_wd - d) % 7
            if days_back == 0 and h >= now.hour:
                skipped.append({"machine": key, "cell": cell, "code": incident,
                                "reason": "current hour or older than the 7-day window"})
                continue
            if incident >= len(INCIDENTES_OPCIONES):
                skipped.append({"machine": key, "cell": cell, "code": incident,
                                "reason": "code not in INCIDENTES_OPCIONES (append it to config.py and redeploy)"})
                continue
            hour_start = (this_hour - timedelta(days=days_back)).replace(hour=h)
            shift_code, date_str, slot = hour_context(hour_start)
            targets.append({
                "machine": code,
                "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                "external_id": f"report_{code}_{date_str}_{shift_code}_entry_{slot:02d}",
                "incident_code": incident,
                "text": INCIDENTES_OPCIONES[incident],
            })
    return targets, skipped


def handle(client=None, data=None):  # noqa: D401 - CDF Functions entry point
    data = data or {}
    dry_run = bool(data.get("dry_run", False))
    max_age = int(data.get("max_age_minutes", MAX_AGE_MINUTES))

    if data.get("snapshot") is not None:
        snap = parse_snapshot(data["snapshot"])
        source = "data.snapshot"
    else:
        try:
            snap = latest_snapshot(client, max_age)
        except CogniteAPIError as e:
            if e.code == 404:
                return {"status": "no_raw_table", "detail": f"{RAW_DB}.{RAW_TABLE} not found: create it and the "
                        f"hosted extractor job (see README). {e.message}", "dry_run": dry_run}
            raise
        source = f"RAW {RAW_DB}.{RAW_TABLE}" + (f" row {snap['raw_key']}" if snap else "")
        if snap is None:
            return {"status": "no_snapshot", "detail": f"no {SNAPSHOT_TAG} in {RAW_DB}.{RAW_TABLE} in the last "
                    f"{max_age} min (plant offline or not publishing): nothing done", "dry_run": dry_run}
        age = datetime.now(timezone.utc) - snap["sent_at_dt"]
        if age > timedelta(minutes=max_age):
            return {"status": "stale_snapshot", "sent_at": snap["sent_at"], "detail": f"newest snapshot is "
                    f"{age} old (> {max_age} min): nothing done", "dry_run": dry_run}

    targets, skipped = cells_to_targets(snap, data.get("machines"))
    events = {}
    if targets:
        found = client.events.retrieve_multiple(external_ids=[t["external_id"] for t in targets],
                                                ignore_unknown_ids=True)
        events = {e.external_id: e for e in found}

    synced_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updates, changes, up_to_date, waiting = [], [], 0, []
    for t in targets:
        evt = events.get(t["external_id"])
        if evt is None:
            waiting.append({k: t[k] for k in ("machine", "hour", "external_id")})
            continue
        meta = dict(evt.metadata or {})
        if evt.type not in (None, EVENT_TYPE):
            skipped.append({"external_id": t["external_id"], "reason": f"event type is {evt.type!r}"})
            continue
        if meta.get("observations") == t["text"] and meta.get("incident_code") == str(t["incident_code"]):
            up_to_date += 1
            continue
        changes.append({"machine": t["machine"], "hour": t["hour"], "external_id": t["external_id"],
                        "from": meta.get("observations"), "to": t["text"], "incident_code": t["incident_code"]})
        upd = EventUpdate(external_id=t["external_id"])
        upd.metadata.add({"observations": t["text"], "observaciones": t["text"],
                          "incident_code": str(t["incident_code"]), "incident_source": "plant",
                          "incident_synced_at": synced_at})
        updates.append(upd)

    if updates and not dry_run:
        client.events.update(updates)

    result = {
        "status": "ok",
        "dry_run": dry_run,
        "source": source,
        "sent_at": snap["sent_at"],
        "reported_cells": len(targets),
        "updated" if not dry_run else "would_update": len(changes),
        "up_to_date": up_to_date,
        "waiting_for_event": len(waiting),
        "skipped": skipped,
        "changes": changes,
        "waiting": waiting,
    }
    print(json.dumps({k: v for k, v in result.items() if k not in ("changes", "waiting")}, ensure_ascii=False))
    return result
