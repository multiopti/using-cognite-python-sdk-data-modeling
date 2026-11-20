"""Offline tests for production_reports_to_s3 (fake CDF client and fake S3; nothing real is read or written).

    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\production_reports_to_s3\\test_handler.py
"""
import hashlib
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

TZ = timezone(timedelta(hours=-4))


def ev(ext_id, local_start, **meta):
    ms = int(local_start.replace(tzinfo=TZ).timestamp() * 1000)
    return SimpleNamespace(external_id=ext_id, start_time=ms, last_updated_time=ms + 3600_000, metadata=meta,
                           type="Production Report")


class FakeEvents:
    def __init__(self, evs):
        self.evs = evs

    def list(self, type, limit, start_time=None, last_updated_time=None):
        out = self.evs
        if start_time:
            out = [e for e in out if start_time["min"] <= e.start_time <= start_time["max"]]
        if last_updated_time:
            out = [e for e in out if e.last_updated_time >= last_updated_time["min"]]
        return out

    def retrieve_multiple(self, external_ids, ignore_unknown_ids):
        ids = set(external_ids)
        return [e for e in self.evs if e.external_id in ids]


class FakeS3:
    def __init__(self):
        self.objects, self.puts = {}, 0

    def head_object(self, Bucket, Key):
        from botocore.exceptions import ClientError
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ETag": '"' + hashlib.md5(self.objects[Key]).hexdigest() + '"'}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body
        self.puts += 1


DAY = datetime(2026, 11, 18)
EVENTS = [
    ev("report_standum32_20261118_day_entry_02", DAY.replace(hour=7), hourly_production="4245", short_cans_per_hour="2",
       trimmer_jams_per_hour="1", total_downtime_min="13.00", merma_kg="0.18", pct_merma="0.45%",
       pct_eficiencia="78.33%", observations="Parada por latas cortas y trancamiento"),
    ev("report_standum32_20261118_day_entry_01", DAY.replace(hour=6), hourly_production="614", pct_eficiencia="50.00%",
       observations="Falla Mecánica", incident_code="1", incident_source="plant"),
    ev("report_p11_20261118_night_entry_09", DAY.replace(hour=2) + timedelta(days=1), hourly_production="5000.0",
       hourly_retrac="3.0", blow_off="1.0", downtime_minutes="10.0", efficiency="75.00%"),
    ev("report_minster_l1_20261118_day_entry_01", DAY.replace(hour=6), golpes_bobina_hora="900", golpes_turno_hora="880",
       hourly_production="880", pct_eficiencia="60.00%", downtime_minutes="20.00"),
    ev("something_else", DAY.replace(hour=6)),
]


def test_row_fields_and_types():
    key, row = handler.event_to_row(EVENTS[0])
    assert key == ("standum32", "2026-11-18", "day")
    assert row["hour_start_local"] == "2026-11-18 07:00:00" and row["hour_start_utc"] == "2026-11-18 11:00:00"
    assert row["hour_label"] == "7AM-8AM" and row["slot"] == 2 and row["line"] == "L3" and row["machine_type"] == "STANDUM"
    assert (row["production"], row["short_cans"], row["scrap_pct"], row["efficiency_pct"]) == (4245.0, 2.0, 0.45, 78.33)
    assert row["retrac"] is None and row["golpes_turno"] is None            # not a STANDUM column
    _, r1 = handler.event_to_row(EVENTS[1])
    assert (r1["observations"], r1["incident_code"], r1["incident_source"]) == ("Falla Mecánica", 1, "plant")


def test_printer_and_minster_columns_and_night_shift():
    key, row = handler.event_to_row(EVENTS[2])
    assert key == ("p11", "2026-11-18", "night") and row["hour_start_local"] == "2026-11-19 02:00:00"
    assert (row["retrac"], row["blow_off"], row["downtime_min"], row["efficiency_pct"]) == (3.0, 1.0, 10.0, 75.0)
    assert row["hour_label"] == "2AM-3AM"
    _, m = handler.event_to_row(EVENTS[3])
    assert (m["golpes_bobina"], m["golpes_turno"], m["production"]) == (900.0, 880.0, 880.0)


def test_non_report_events_are_ignored():
    assert handler.event_to_row(EVENTS[4]) is None


def test_hour_labels():
    assert [handler._hour_label(h) for h in (0, 6, 11, 12, 13, 23)] == \
        ["12AM-1AM", "6AM-7AM", "11AM-12PM", "12PM-1PM", "1PM-2PM", "11PM-12AM"]


def test_backfill_groups_one_file_per_machine_shift_sorted_by_slot():
    client = SimpleNamespace(events=FakeEvents(EVENTS))
    files = handler.collect(client, {"from": "2026-11-18", "to": "2026-11-18"})
    assert set(files) == {("standum32", "2026-11-18", "day"), ("p11", "2026-11-18", "night"),
                          ("minster_l1", "2026-11-18", "day")}
    body = handler.shift_file(files[("standum32", "2026-11-18", "day")]).decode("utf-8").splitlines()
    assert [json.loads(l)["slot"] for l in body] == [1, 2]
    assert handler.s3_key("standum32", "2026-11-18", "day") == \
        "production_hourly/shift_date=2026-11-18/shift=day/standum32.jsonl"


def test_backfill_excludes_the_previous_days_night_hours():
    # 02:00 on the 18th belongs to the night shift of the 17th, outside a backfill of the 18th only
    e = ev("report_p11_20261117_night_entry_09", DAY.replace(hour=2), hourly_production="1")
    files = handler.collect(SimpleNamespace(events=FakeEvents([e])), {"from": "2026-11-18", "to": "2026-11-18"})
    assert files == {}


def test_machines_filter():
    files = handler.collect(SimpleNamespace(events=FakeEvents(EVENTS)),
                            {"from": "2026-11-18", "to": "2026-11-18", "machines": ["P11"]})
    assert set(files) == {("p11", "2026-11-18", "night")}


def test_upload_only_when_changed(monkeypatch=None):
    s3 = FakeS3()
    handler._s3 = lambda secrets: s3
    client = SimpleNamespace(events=FakeEvents(EVENTS))
    data = {"from": "2026-11-18", "to": "2026-11-18"}
    r1 = handler.handle(client, data)
    assert (r1["uploaded"], r1["unchanged"], s3.puts) == (3, 0, 3)
    r2 = handler.handle(client, data)                                    # same content: nothing uploaded
    assert (r2["uploaded"], r2["unchanged"], s3.puts) == (0, 3, 3)
    EVENTS[0].metadata["observations"] = "Falla Eléctrica"               # an incident arrives -> that file only
    r3 = handler.handle(client, data)
    assert (r3["uploaded"], r3["unchanged"]) == (1, 2)


def test_dry_run_uploads_nothing():
    s3 = FakeS3()
    handler._s3 = lambda secrets: s3
    r = handler.handle(SimpleNamespace(events=FakeEvents(EVENTS)), {"from": "2026-11-18", "to": "2026-11-18",
                                                                    "dry_run": True})
    assert r["files"] == 3 and s3.puts == 0 and r["sample_row"]["machine"] in ("minster_l1", "p11", "standum32")


def test_machine_map_matches_hourly_report_config():
    spec = importlib.util.spec_from_file_location("hpr_config", THIS_DIR.parent / "hourly_production_report" / "config.py")
    hc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hc)
    expected = {c["code"].lower(): (c["line"], c["machine_type"].upper()) for c in hc.MACHINE_CONFIGS}
    assert config.MACHINES == expected


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
