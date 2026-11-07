"""
Per-machine production summary of one shift, read from the hourly
"Production Report" events (report_{code}_{YYYYMMDD}_{day|night}_entry_{01..12}).

Prints one pipe-separated row per machine: hours with an event, active hours,
production, scrap, mean efficiency over active hours, downtime minutes, and
the latest datapoint of its production series (-1001 = PLC comm error).

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python utils\\shift_summary.py 20261029 night
"""
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "streamlit"))
sys.path.insert(0, str(REPO / "functions" / "shift_reconciler"))

from cdf_auth import get_client  # noqa: E402
from config import MACHINE_CONFIGS, LOCAL_TZ  # noqa: E402

DATE, SHIFT = sys.argv[1], sys.argv[2]  # e.g. 20261028 night
client = get_client()

ext_ids = [f"report_{c['code']}_{DATE}_{SHIFT}_entry_{s:02d}" for c in MACHINE_CONFIGS for s in range(1, 13)]
events = {e.external_id: e for e in client.events.retrieve_multiple(external_ids=ext_ids, ignore_unknown_ids=True)}

prod_ts = {c["code"]: c.get("ts_prod") or c.get("ts_golpes_bob") for c in MACHINE_CONFIGS}
latest = client.time_series.data.retrieve_latest(external_id=list(prod_ts.values()), ignore_unknown_ids=True)
latest_by = {d.external_id: d for d in latest}


def num(v):
    try:
        return float(str(v).replace("%", ""))
    except Exception:
        return 0.0


print("code|line|type|hours_with_event|hours_active|production|scrap|avg_eff_active|downtime|last_value|last_ts_local")
for c in MACHINE_CONFIGS:
    prod = scrap = dt = eff = 0.0
    n_ev = n_act = 0
    for s in range(1, 13):
        e = events.get(f"report_{c['code']}_{DATE}_{SHIFT}_entry_{s:02d}")
        if not e:
            continue
        m = e.metadata or {}
        n_ev += 1
        p = num(m.get("hourly_production", m.get("golpes_bobina_hora", 0)))
        prod += p
        scrap += sum(num(m.get(k, 0)) for k in ("short_cans_per_hour", "trimmer_jams_per_hour", "hourly_retrac", "blow_off"))
        dt += num(m.get("downtime_minutes", m.get("total_downtime_min", 0)))
        if p > 0:
            n_act += 1
            eff += num(m.get("pct_eficiencia", m.get("efficiency", 0)))
    d = latest_by.get(prod_ts[c["code"]])
    lv, lt = ("-", "-")
    if d is not None and getattr(d, "timestamp", None) is not None:
        ts = d.timestamp if not isinstance(d.timestamp, (list, tuple)) else d.timestamp[0]
        lv = d.value if not isinstance(d.value, (list, tuple)) else d.value[0]
        ts = ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts / 1000, LOCAL_TZ)
        lt = ts.astimezone(LOCAL_TZ).strftime("%m-%d %H:%M")
    print(f"{c['code']}|{c['line']}|{c['machine_type']}|{n_ev}|{n_act}|{prod:.0f}|{scrap:.0f}|{(eff / n_act if n_act else 0):.1f}|{dt:.0f}|{lv}|{lt}")
