"""Plant data for the local Streamlit apps, read from the plant's Node-RED instead of CDF.

Node-RED (GET /api/data_week) holds one weekly matrix per counter: 168 values, index = weekday * 24 + hour
(Sunday = 0), each the counter at minute 59 of that hour, -1 = no data, -1001 = PLC communication error.
They come from the Optix TimeUpdater, so only the last 7 days are available and the newest complete hour is the
one that ended at the last hh:59 -- the same hourly cadence as the CDF Production Report events.

From those matrices this module rebuilds what the apps used to read from CDF:
  - hourly report rows per machine, with the same formulas and constants as
    functions/hourly_production_report (its MACHINE_CONFIGS and config are reused, not copied);
  - shift-to-date totals per machine and per line/type (LINE1_PRINTER_PRODUCTION_SHIFT, ...).
One difference on purpose: production during a data gap (power cut, -1 hours) is attributed to the first hour
after the gap, so shift totals stay complete; the CDF function only sums increases seen inside each hour.

Settings (environment): PLANT_NODERED_URL (default http://127.0.0.1:1880).
"""
import importlib.util
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent                       # cognite-sdk/
NODERED_URL = os.environ.get("PLANT_NODERED_URL", "http://127.0.0.1:1880").rstrip("/")
LOCAL_TZ = timezone(timedelta(hours=-4))
CACHE_S = 30           # one Node-RED read serves every viewer for this long (Node-RED itself re-reads every 5 min)
STALE_S = 15 * 60      # last good read older than this -> status shown as a problem

# functions/hourly_production_report/config.py, loaded under its own name: the apps have their own "config" module
_spec = importlib.util.spec_from_file_location(
    "hourly_report_config", ROOT / "functions" / "hourly_production_report" / "config.py")
HR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HR)


def _key(ts_name):
    """CDF series name -> Node-RED Data_Week key, e.g. STANDUM31_PROD_LATAS_CORTAS_ACT_DISP -> STANDUM31_LATAS_CORTAS."""
    if not ts_name:
        return None
    k = re.sub(r"_(ACT|ACUM)_DISP$", "", ts_name)
    k = k.replace("_PROD_LATAS_CORTAS", "_LATAS_CORTAS")
    return re.sub(r"_PROD$", "", k)


MACHINES = {}
for _cfg in HR.MACHINE_CONFIGS:
    _keys = {name[3:]: _key(ts) for name, ts in _cfg.items() if name.startswith("ts_")}
    MACHINES[_cfg["code"].lower()] = {
        "code": _cfg["code"].lower(),
        "type": _cfg["machine_type"].upper(),
        "line": _cfg["line"],
        "capacity": float(_cfg.get("nominal_capacity") or 0.0),
        "keys": _keys,
        # hourly incident matrix (Optix Model/OBSERVACIONES/<base>_OBS_DATA_WEEK): DI11_OBS, MINSTER_L1_OBS, ...
        "obs_machine": _keys.get("prod") or _cfg["code"].upper(),
    }
# counters that do NOT restart with the shift (strokes per coil): their first hour is measured against the
# previous hour, even across the shift change
CONTINUOUS = {"golpes_bob"}


# ------------------------------------------------------------------ reading Node-RED
_lock = threading.Lock()
_cache = {"read_at": 0.0, "week": None, "ok_at": None, "error": None}


def _flat(v):
    if isinstance(v, dict):                       # serialised Int32Array {"0": .., "167": ..}
        return [v.get(str(i)) for i in range(168)]
    if v and isinstance(v[0], list):              # [7][24]
        return [x for row in v for x in row]
    return list(v)


def data_week():
    """{key: [168 ints]} from Node-RED, cached CACHE_S seconds. If Node-RED is down, the last good data is kept
    (status() reports it); with no data at all a RuntimeError explains the problem."""
    with _lock:
        now = time.time()
        if now - _cache["read_at"] >= CACHE_S:
            _cache["read_at"] = now
            try:
                with urllib.request.urlopen(NODERED_URL + "/api/data_week", timeout=5) as r:
                    body = json.loads(r.read())
                _cache["week"] = {k: _flat(v) for k, v in (body.get("data_week") or {}).items()}
                _cache["ok_at"] = datetime.now(LOCAL_TZ)
                _cache["error"] = None
            except Exception as e:
                _cache["error"] = f"{type(e).__name__}: {e}"
        if _cache["week"] is None:
            raise RuntimeError(f"No se pudo leer el servidor Node-RED ({NODERED_URL}/api/data_week): {_cache['error']}")
        return _cache["week"]


def invalidate():
    """Forget the cached read, so the next call reads Node-RED again (e.g. right after saving an incident)."""
    with _lock:
        _cache["read_at"] = 0.0


def save_incident(code_machine, shift_date, shift_code, slot, incident_code):
    """Store an hour's incident code in Optix through Node-RED (POST /api/observacion). incident_code -1 clears it.
    Raises RuntimeError with Node-RED's explanation when it is refused."""
    machine = MACHINES[code_machine.lower()]["obs_machine"]
    d = shift_hours(shift_date, shift_code)[0].date()
    body = json.dumps({"machine": machine, "date": d.strftime("%Y-%m-%d"), "shift": shift_code,
                       "slot": int(slot), "code": int(incident_code)}).encode("utf-8")
    req = urllib.request.Request(NODERED_URL + "/api/observacion", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            answer = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            answer = json.loads(e.read() or b"{}")
        except ValueError:
            answer = {"error": f"HTTP {e.code}"}
    except Exception as e:
        raise RuntimeError(f"no se pudo contactar a Node-RED ({NODERED_URL}): {e}")
    if not answer.get("ok"):
        raise RuntimeError(answer.get("error") or "Node-RED rechazó la incidencia")
    return answer


def status():
    """(ok, text) about the last read from Node-RED, for the apps' status line."""
    try:
        week = data_week()
    except RuntimeError as e:
        return False, str(e)
    ok_at, err = _cache["ok_at"], _cache["error"]
    age = (datetime.now(LOCAL_TZ) - ok_at).total_seconds()
    text = f"Node-RED: datos leídos {ok_at:%d/%m/%Y %H:%M:%S} ({len(week)} matrices)"
    if err:
        text += f" -- última lectura falló: {err}"
    return age < STALE_S and not err, text


# ------------------------------------------------------------------ hours and shifts
def shift_hours(shift_date, shift_code):
    """The 12 hour starts (local, aware) of a shift. shift_code 'day' = 06-18, 'night' = 18-06 (+1 day)."""
    d = shift_date if isinstance(shift_date, date) else datetime.strptime(str(shift_date)[:10].replace("-", ""), "%Y%m%d").date()
    start = datetime(d.year, d.month, d.day, 6 if shift_code == "day" else 18, tzinfo=LOCAL_TZ)
    return [start + timedelta(hours=i) for i in range(12)]


def current_shift(now=None):
    now = now or datetime.now(LOCAL_TZ)
    if 6 <= now.hour < 18:
        return now.date(), "day"
    return (now.date() if now.hour >= 18 else now.date() - timedelta(days=1)), "night"


def oldest_date(now=None):
    """Oldest day whose hours the weekly matrices still hold (today's slot of 7 days ago is already reused)."""
    return (now or datetime.now(LOCAL_TZ)).date() - timedelta(days=6)


def _available(hour_start, now):
    """The matrix holds this hour: it has finished and is not older than the 7-day window."""
    return hour_start + timedelta(hours=1) <= now and hour_start.date() >= oldest_date(now)


def _value(series, hour_start):
    v = series[((hour_start.weekday() + 1) % 7) * 24 + hour_start.hour] if series else None
    return v if isinstance(v, (int, float)) and v >= 0 else None      # -1 / -1001 / missing -> None


def hourly(series, hours, continuous=False, now=None):
    """Production of each hour from a counter matrix. Returns a list (one per hour) of:
       a number, None (hour finished but no data: Optix off or PLC error), or "pending" (not finished yet).
    Shift counters restart at 06:00/18:00: the first hour with data is the counter itself. A counter that went down
    restarted inside that hour (the whole value is that hour's). Hours without data are skipped and their production
    lands in the next hour with data."""
    now = now or datetime.now(LOCAL_TZ)
    last = None
    if continuous:                                   # e.g. strokes per coil: start from the hour before the shift
        back = hours[0] - timedelta(hours=1)
        for _ in range(12):
            if _available(back, now) and _value(series, back) is not None:
                last = _value(series, back)
                break
            back -= timedelta(hours=1)
    out = []
    for h in hours:
        if not _available(h, now):
            out.append("pending" if h + timedelta(hours=1) > now else None)
            continue
        v = _value(series, h)
        if v is None:
            out.append(None)
            continue
        out.append(v if last is None or v < last else v - last)
        last = v
    return out


# ------------------------------------------------------------------ report rows (same math as hourly_production_report)
def _fmt_pct(x):
    return f"{x:.2f}%"


def hour_report(machine, counts):
    """Report fields of one hour from its counter increments (dict: prod, retract, blow_off, short_cans,
    trimmer_jams, golpes_bob, golpes_turno -> number). Mirrors generate_*_event in hourly_production_report."""
    t, cap = machine["type"], machine["capacity"]
    if t == "PRINTER":
        prod, retrac, blow = counts.get("prod", 0.0), counts.get("retract", 0.0), counts.get("blow_off", 0.0)
        downtime = max(0.0, round(60.0 - prod * 60.0 / cap, 2)) if cap > 0 else 60.0
        eff = round(prod * 100.0 / cap, 2) if cap > 0 else 0.0
        return {"production": prod, "scrap": retrac + blow, "downtime": downtime, "efficiency": eff,
                "row": {"Producción x hora": prod, "Retrac-x-hora": retrac, "Blow of": blow,
                        "Tiempo de parada": downtime, "% Eficiencia": _fmt_pct(eff)}}
    if t in ("DI", "STANDUM"):
        prod, short, trim = counts.get("prod", 0.0), counts.get("short_cans", 0.0), counts.get("trimmer_jams", 0.0)
        cans_short, cans_trim = short * HR.CANS_PER_SHORT_CAN, trim * HR.CANS_PER_TRIMMER_JAM
        dt_short, dt_trim = short * HR.DOWNTIME_PER_SHORT_CAN_MIN, trim * HR.DOWNTIME_PER_TRIM_JAM_MIN
        downtime = 60.0 if prod == 0 else min(60.0, dt_short + dt_trim)
        scrap_cans = cans_short + cans_trim
        merma_kg = round(scrap_cans * HR.CAN_WEIGHT_KG, 2)
        pct_merma = round(scrap_cans / (prod + scrap_cans) * 100.0, 2) if prod + scrap_cans > 0 else 0.0
        eff = round((60.0 - downtime) / 60.0 * 100.0, 2)
        if prod == 0:
            obs = "Sin producción"
        elif downtime == 0:
            obs = "Operación normal"
        elif short > 0 and trim > 0:
            obs = "Parada por latas cortas y trancamiento"
        elif short > 0:
            obs = "Parada por latas cortas"
        else:
            obs = "Parada por trancamiento trimmer"
        return {"production": prod, "scrap": short + trim, "downtime": downtime, "efficiency": eff, "obs": obs,
                "row": {"PROD. LATAS": prod, "LAT CORTAS": short, "TRANC TRIMMER": trim,
                        "LAT x LAT CORTAS": cans_short, "LAT x TRANC TRIM": cans_trim,
                        "Tiempo prom de parada x lat cort (min)": round(dt_short, 2),
                        "Tiempo prom de parada x tranc trim (min)": round(dt_trim, 2),
                        "Tiempo parada (min)": round(downtime, 2), "Merma (kg)": merma_kg,
                        "% Merma": _fmt_pct(pct_merma), "% Eficiencia": _fmt_pct(eff)}}
    if t == "MINSTER":
        bob, turno = counts.get("golpes_bob", 0.0), counts.get("golpes_turno", 0.0)
        cap = cap or 120000.0
        eff = round(bob * 100.0 / cap, 2) if cap > 0 else 0.0
        downtime = max(0.0, round(60.0 - bob * 60.0 / cap, 2)) if cap > 0 else 0.0
        return {"production": bob, "scrap": None, "downtime": downtime, "efficiency": eff,
                "obs": "Sin producción" if bob == 0 else "Operación normal",
                "row": {"Golpes Bobina": bob, "Golpes Turno": turno, "Tiempo Parada (min)": downtime,
                        "% Eficiencia": _fmt_pct(eff)}}
    # ISPRAY
    prod = counts.get("prod", 0.0)
    cap = cap or 30000.0
    eff = round(prod * 100.0 / cap, 2) if cap > 0 else 0.0
    downtime = max(0.0, round(60.0 - prod * 60.0 / cap, 2)) if cap > 0 else 0.0
    return {"production": prod, "scrap": None, "downtime": downtime, "efficiency": eff,
            "obs": "Sin producción" if prod == 0 else "Operación normal",
            "row": {"Producción x hora": prod, "Tiempo Parada (min)": downtime, "% Eficiencia": _fmt_pct(eff)}}


def shift_report(code, shift_date, shift_code, now=None):
    """[{slot, hour_start, status: 'ok'|'no_data'|'pending', ...hour_report fields}] for the 12 hours of a shift."""
    now = now or datetime.now(LOCAL_TZ)
    machine = MACHINES[code.lower()]
    week = data_week()
    hours = shift_hours(shift_date, shift_code)
    per_counter = {name: hourly(week.get(key), hours, continuous=name in CONTINUOUS, now=now)
                   for name, key in machine["keys"].items()}
    main = "golpes_bob" if machine["type"] == "MINSTER" else "prod"
    obs_series = week.get(machine["obs_machine"] + "_OBS")
    out = []
    for i, h in enumerate(hours):
        state = per_counter[main][i]
        if state == "pending":
            out.append({"slot": i + 1, "hour_start": h, "status": "pending"})
            continue
        incident = _value(obs_series, h) if _available(h, now) else None   # code chosen by an operator, or None
        counts = {name: (vals[i] if isinstance(vals[i], (int, float)) else 0.0) for name, vals in per_counter.items()}
        rep = hour_report(machine, counts)
        rep.update(slot=i + 1, hour_start=h, status="ok" if state is not None else "no_data", incident=incident)
        if state is None:
            rep["obs"] = "Sin datos (Optix apagado o error de comunicación con el PLC)"
        out.append(rep)
    return out


def machine_shift_totals(codes, now=None):
    """{code: {"production": x, "scrap": y}} for the shift running now (finished hours), like the plant views'
    CDF version summed this shift's Production Report events. Scrap is 0 for MINSTER/ISPRAY."""
    now = now or datetime.now(LOCAL_TZ)
    d, s = current_shift(now)
    out = {}
    for code in codes:
        if code.lower() not in MACHINES:
            continue
        rows = [r for r in shift_report(code, d, s, now) if r["status"] == "ok"]
        out[code] = {"production": float(sum(r["production"] for r in rows)),
                     "scrap": float(sum(r["scrap"] or 0.0 for r in rows))}
    return out


def line_values(targets, now=None):
    """{target: value} for LINE<n>[_<TYPE>]_(PRODUCTION|SCRAP)_SHIFT names, shift-to-date, like the CDF rollups."""
    now = now or datetime.now(LOCAL_TZ)
    totals = {}
    for target in targets:
        m = re.fullmatch(r"LINE(\d)(?:_([A-Z]+))?_(PRODUCTION|SCRAP)_SHIFT", target or "")
        if not m:
            continue
        line, mtype, what = f"L{m.group(1)}", m.group(2), m.group(3).lower()
        codes = [c for c, mc in MACHINES.items() if mc["line"] == line and (mtype is None or mc["type"] == mtype)]
        per = machine_shift_totals(codes, now)
        if what == "scrap" and all(MACHINES[c]["type"] in ("MINSTER", "ISPRAY") for c in codes):
            continue                                   # no scrap series exists for these types
        totals[target] = float(sum(v["production" if what == "production" else "scrap"] for v in per.values()))
    return totals
