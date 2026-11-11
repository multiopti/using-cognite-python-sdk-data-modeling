"""
Local DRY RUN of plant_incident_sync against the REAL CDF project (reads only; dry_run=True writes nothing), using
the same .env auth helper as the Streamlit app (../../streamlit/cdf_auth.py).

Three checks:
  1. a real snapshot captured from the plant_simulation Optix (2026-11-10, STANDUM32 incidents on Thu 2026-11-05):
     which real Production Report events it maps to and what would change;
  2. a snapshot built NOW with one incident yesterday at 10:00 (day) and 20:00 (night) on a few machines, so the
     mapping is checked against recent events;
  3. reading RAW: until the hosted extractor job and the table exist this reports "no_raw_table".

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\plant_incident_sync\\local_test.py
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR.parents[1] / "streamlit"))
sys.path.insert(0, str(THIS_DIR))

from config import LOCAL_TZ  # noqa: E402
from handler import handle  # noqa: E402
from cdf_auth import get_client  # noqa: E402

SIM_SAMPLE = ('{"v":1,"sent_at":"2026-11-10T21:18:54-04:00","cells":{"STANDUM32":[[102,0],[103,0],[104,1],[105,1],'
              '[106,2],[107,2],[108,5],[109,5],[110,11],[111,11],[112,12],[113,12]]}}')


def show(title, res):
    print(f"\n=== {title}")
    print(json.dumps({k: v for k, v in res.items() if k not in ("changes", "waiting")}, indent=1, ensure_ascii=False))
    for c in res.get("changes", [])[:20]:
        print(f"  WOULD CHANGE {c['external_id']}  ({c['hour']}): {c['from']!r} -> {c['to']!r}")
    for w in res.get("waiting", [])[:20]:
        print(f"  WAITING (no event yet) {w['external_id']}  ({w['hour']})")


if __name__ == "__main__":
    client = get_client()
    show("1. snapshot from the simulation", handle(client, {"snapshot": SIM_SAMPLE, "dry_run": True}))

    now = datetime.now(LOCAL_TZ).replace(microsecond=0)
    yday_wd = (now - timedelta(days=1)).isoweekday() % 7            # Sunday = 0
    cells = {"DI11": [[yday_wd * 24 + 10, 1]], "STANDUM31": [[yday_wd * 24 + 20, 2]],
             "MINSTER_L1": [[yday_wd * 24 + 10, 7]], "PRINTER_L1": [[yday_wd * 24 + 20, 0]]}
    show("2. snapshot built now (yesterday 10:00 / 20:00)",
         handle(client, {"snapshot": {"v": 1, "sent_at": now.isoformat(), "cells": cells}, "dry_run": True}))

    show("3. reading RAW", handle(client, {"dry_run": True}))
