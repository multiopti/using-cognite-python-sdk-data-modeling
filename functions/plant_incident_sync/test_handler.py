"""Offline tests for plant_incident_sync (fake CDF client, nothing is read from or written to CDF).

    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\plant_incident_sync\\test_handler.py
(or with pytest, if installed)
"""
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

import config  # noqa: E402
import handler  # noqa: E402

# a real message received from the plant_simulation Optix through the local broker (2026-11-10)
SAMPLE = ('{"v":1,"sent_at":"2026-11-10T21:18:54-04:00","cells":{"STANDUM32":[[102,0],[103,0],[104,1],[105,1],'
          '[106,2],[107,2],[108,5],[109,5],[110,11],[111,11],[112,12],[113,12]]}}')


class FakeEvents:
    def __init__(self, events):
        self.events = {e.external_id: e for e in events}
        self.updated = []

    def retrieve_multiple(self, external_ids, ignore_unknown_ids):
        assert ignore_unknown_ids
        return [self.events[x] for x in external_ids if x in self.events]

    def update(self, updates):
        self.updated.extend(updates)


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def list(self, db, table, min_last_updated_time, limit):
        assert (db, table) == (config.RAW_DB, config.RAW_TABLE)
        return self.rows


def fake_client(events=(), rows=()):
    return SimpleNamespace(events=FakeEvents(events), raw=SimpleNamespace(rows=FakeRows(list(rows))))


def event(ext_id, observations="Operación normal", **meta):
    return SimpleNamespace(external_id=ext_id, type=config.EVENT_TYPE,
                           metadata={"observations": observations, "hourly_production": "1000", **meta})


def snapshot(sent_at, cells):
    return {"v": 1, "sent_at": sent_at, "cells": cells}


def test_sample_maps_to_thursday_day_shift():
    targets, skipped = handler.cells_to_targets(handler.parse_snapshot(SAMPLE))
    assert not skipped
    ids = [t["external_id"] for t in targets]
    # sent Tue 2026-11-10; cells 102..113 = Thursday (4) 06:00..17:00 -> Thu 2026-11-05 day shift, slots 1..12
    assert ids == [f"report_standum32_20261105_day_entry_{s:02d}" for s in range(1, 13)]
    assert [t["text"] for t in targets[:3]] == ["Operación estándar", "Operación estándar", "Falla Mecánica"]
    assert targets[-1]["text"] == "Sin Personal / Ausentismo"


def test_night_hours_and_todays_column():
    # Tuesday 2026-11-10 21:18 (weekday 2 -> cells 48..71 are today)
    snap = handler.parse_snapshot(snapshot("2026-11-10T21:18:54-04:00", {"DI11": [
        [26, 1],    # Mon 02:00 -> night shift of Sun 11-08, slot 9
        [43, 2],    # Mon 19:00 -> night shift of Mon 11-09, slot 2
        [68, 3],    # today 20:00 -> night shift of Tue 11-10, slot 3
        [69, 4],    # today 21:00: current hour, unfinished -> skipped
        [70, 5],    # today 22:00: 7 days ago, wiped column -> skipped
        [6, 6],     # Sun 06:00 -> day shift of Sun 11-08, slot 1
    ]}))
    targets, skipped = handler.cells_to_targets(snap)
    assert [t["external_id"] for t in targets] == [
        "report_di11_20261108_night_entry_09", "report_di11_20261109_night_entry_02",
        "report_di11_20261110_night_entry_03", "report_di11_20261108_day_entry_01"]
    assert sorted(s["cell"] for s in skipped) == [69, 70]


def test_hour_context_matches_hourly_production_report():
    spec = importlib.util.spec_from_file_location("hpr_handler", THIS_DIR.parent / "hourly_production_report" / "handler.py")
    sys.path.insert(0, str(THIS_DIR.parent / "hourly_production_report"))
    saved = sys.modules.pop("config")                       # the hourly function has its own config module
    try:
        hpr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hpr)
    finally:
        sys.modules["config"] = saved
        sys.path.remove(str(THIS_DIR.parent / "hourly_production_report"))
    start = datetime(2026, 11, 8, 0, 0)
    for i in range(48):
        h = start + timedelta(hours=i)
        ctx = hpr._shift_context(h)
        assert handler.hour_context(h) == (ctx["shift_code"], ctx["date_str"], int(ctx["entry_slot"])), h


def test_unknown_machine_and_code_are_reported_not_written():
    snap = handler.parse_snapshot(snapshot("2026-11-10T21:18:54-04:00",
                                           {"XX99": [[30, 1]], "DI12": [[30, len(config.INCIDENTES_OPCIONES)]]}))
    targets, skipped = handler.cells_to_targets(snap)
    assert targets == []
    assert {s["reason"].split(" (")[0] for s in skipped} == {"unknown machine key", "code not in INCIDENTES_OPCIONES"}


def test_updates_only_what_differs_and_waits_for_missing_events():
    snap = snapshot("2026-11-10T21:18:54-04:00", {"DI11": [[34, 2], [35, 3], [36, 4]]})   # Mon 10:00, 11:00, 12:00
    client = fake_client(events=[
        event("report_di11_20261109_day_entry_05"),                                         # automatic text -> update
        event("report_di11_20261109_day_entry_06", "Falla Neumática / Hidráulica", incident_code="3"),  # up to date
        # entry_07 (12:00) doesn't exist yet -> waits
    ])
    res = handler.handle(client, {"snapshot": snap})
    assert (res["updated"], res["up_to_date"], res["waiting_for_event"]) == (1, 1, 1)
    assert res["changes"][0]["from"] == "Operación normal" and res["changes"][0]["to"] == "Falla Eléctrica"
    [upd] = client.events.updated
    dumped = upd.dump()
    assert dumped["externalId"] == "report_di11_20261109_day_entry_05"
    added = dumped["update"]["metadata"]["add"]
    assert added["observations"] == added["observaciones"] == "Falla Eléctrica"
    assert added["incident_code"] == "2" and added["incident_source"] == "plant"
    assert "set" not in dumped["update"]["metadata"]                 # the rest of the metadata is kept


def test_changed_code_overwrites_and_rerun_writes_nothing():
    snap = snapshot("2026-11-10T21:18:54-04:00", {"DI11": [[34, 5]]})
    evt = event("report_di11_20261109_day_entry_05", "Falla Eléctrica", incident_code="2")
    client = fake_client(events=[evt])
    assert handler.handle(client, {"snapshot": snap})["updated"] == 1
    evt.metadata.update(client.events.updated[0].dump()["update"]["metadata"]["add"])
    client2 = fake_client(events=[evt])
    res = handler.handle(client2, {"snapshot": snap})
    assert (res["updated"], res["up_to_date"]) == (0, 1) and client2.events.updated == []


def test_hourly_rerun_text_is_restored():
    # hourly_production_report re-ran the hour: observations back to automatic text, incident_code still there
    snap = snapshot("2026-11-10T21:18:54-04:00", {"DI11": [[34, 2]]})
    client = fake_client(events=[event("report_di11_20261109_day_entry_05", "Operación normal", incident_code="2")])
    assert handler.handle(client, {"snapshot": snap})["updated"] == 1


def test_dry_run_writes_nothing():
    client = fake_client(events=[event("report_standum32_20261105_day_entry_01")])
    res = handler.handle(client, {"snapshot": SAMPLE, "dry_run": True})
    assert res["would_update"] == 1 and res["waiting_for_event"] == 11 and client.events.updated == []


def test_machines_filter():
    snap = snapshot("2026-11-10T21:18:54-04:00", {"DI11": [[34, 2]], "DI12": [[34, 2]]})
    targets, _ = handler.cells_to_targets(handler.parse_snapshot(snap), machines=["DI12"])
    assert [t["machine"] for t in targets] == ["di12"]


def test_raw_newest_snapshot_is_used_and_old_ones_ignored():
    now = datetime.now(timezone(timedelta(hours=-4))).replace(microsecond=0)

    def row(key, sent_at, cells):
        value = json.dumps(snapshot(sent_at.isoformat(), cells))
        return SimpleNamespace(key=key, columns={"topic": "SuperenvasesIncidents/snapshot", "timestamp": "x",
                                                 "records": [{"TagName": "INCIDENTS_SNAPSHOT", "Value": value}]})
    yday_10 = ((now - timedelta(days=1)).isoweekday() % 7) * 24 + 10
    rows = [row("old", now - timedelta(minutes=10), {"DI11": [[yday_10, 1]]}),
            row("new", now - timedelta(minutes=5), {"DI11": [[yday_10, 2]]})]
    res = handler.handle(fake_client(rows=rows), {"dry_run": True})
    assert res["source"].endswith("row new") and res["waiting"][0]["external_id"].startswith("report_di11_")
    stale = [row("stale", now - timedelta(minutes=45), {"DI11": [[yday_10, 1]]})]
    assert handler.handle(fake_client(rows=stale), {})["status"] == "stale_snapshot"
    assert handler.handle(fake_client(rows=[]), {})["status"] == "no_snapshot"


def test_incident_list_matches_the_reporte():
    spec = importlib.util.spec_from_file_location("reporte_config", THIS_DIR.parents[1] / "streamlit" / "config.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    assert config.INCIDENTES_OPCIONES == rc.INCIDENTES_OPCIONES


def test_machine_map_matches_hourly_report_config():
    spec = importlib.util.spec_from_file_location("hpr_config", THIS_DIR.parent / "hourly_production_report" / "config.py")
    hc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hc)
    assert sorted(config.OBS_KEY_TO_CODE.values()) == sorted(c["code"].lower() for c in hc.MACHINE_CONFIGS)
    assert len(config.OBS_KEY_TO_CODE) == 32


if __name__ == "__main__":
    import contextlib
    import io
    import traceback
    failed = 0
    for name, fn in [(n, f) for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                fn()
            print(f"OK    {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}\n{traceback.format_exc()}")
    print(f"{failed} failed" if failed else "all passed")
    sys.exit(1 if failed else 0)
