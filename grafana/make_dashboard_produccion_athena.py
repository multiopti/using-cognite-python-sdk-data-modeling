"""Builds grafana/dashboard_produccion_athena.json: the Streamlit "Reporte de Producción" in Grafana, reading the hourly
reports that production_reports_to_s3 copies to S3, through Amazon Athena (table polar_production.production_hourly,
workgroup polar-grafana).

Layout (as the Streamlit Reporte):
  - selectors: shift date, shift, machine type, machine;
  - hourly production and a per-type second chart (scrap for D&I/STANDUM, retrac/blow off for PRINTER, downtime for
    ISPRAY/MINSTER);
  - 4 gauges: production vs the machine's capacity for the 12 hours, two per-type indicators, downtime vs 720 min;
  - the hourly table, with each machine type's own columns (as Streamlit), efficiency coloured, incidents highlighted;
  - collapsed row "Datos para descargar": detail and shift totals for any time range and several machines.
Per-type parts come from small hidden Athena variables (SELECT CASE '${tipo}' ... without FROM: nothing scanned).
Any panel downloads as CSV from its menu: Inspect > Data > Download CSV ("Download for Excel").

    python grafana/make_dashboard_produccion_athena.py          # writes the JSON
    python grafana/make_dashboard_produccion_athena.py --sql    # also writes every query, per machine type, with
                                                                # sample values, to %TEMP% for testing in Athena
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
T = "polar_production.production_hourly"
DS = {"type": "grafana-athena-datasource", "uid": "${ds}"}
# "__default" = use the data source's own settings (region us-east-1, catalog AwsDataCatalog, database polar_production,
# workgroup polar-grafana). Explicit values here make the plugin open a separate connection WITHOUT the data source's
# workgroup, and Athena rejects it ("Value at 'workGroup' failed to satisfy constraint"). Table names are fully
# qualified in every query, so nothing depends on the default database.
CONN = {"region": "__default", "catalog": "__default", "database": "__default",
        "resultReuseEnabled": False, "resultReuseMaxAgeInMinutes": 60}
SHIFT = f"FROM {T} WHERE shift_date = '${{fecha}}' AND shift = '${{turno}}' AND machine = '${{maquina}}'"
# Download period, counted from the selected shift date (the time picker is hidden). '${periodo}' is a literal, so
# Athena folds the OR to one branch and still prunes partitions (shift_date / shift).
PERIODS = [("Turno seleccionado", "turno"), ("Día seleccionado (2 turnos)", "dia"),
           ("7 días hasta la fecha", "7d"), ("30 días hasta la fecha", "30d"),
           ("Mes de la fecha", "mes"), ("Mes anterior", "mes_ant")]
RANGE = ("machine IN (${descarga:singlequote}) AND ("
         "('${periodo}' = 'turno' AND shift_date = '${fecha}' AND shift = '${turno}') "
         "OR ('${periodo}' = 'dia' AND shift_date = '${fecha}') "
         "OR ('${periodo}' = '7d' AND shift_date BETWEEN date_format(date('${fecha}') - interval '6' day, '%Y-%m-%d') "
         "AND '${fecha}') "
         "OR ('${periodo}' = '30d' AND shift_date BETWEEN date_format(date('${fecha}') - interval '29' day, '%Y-%m-%d') "
         "AND '${fecha}') "
         "OR ('${periodo}' = 'mes' AND shift_date BETWEEN date_format(date_trunc('month', date('${fecha}')), '%Y-%m-%d') "
         "AND '${fecha}') "
         "OR ('${periodo}' = 'mes_ant' AND shift_date BETWEEN "
         "date_format(date_trunc('month', date('${fecha}')) - interval '1' month, '%Y-%m-%d') "
         "AND date_format(date_trunc('month', date('${fecha}')) - interval '1' day, '%Y-%m-%d')))")
INSTRUCTIONS = ("Reporte horario por máquina y turno. Elija fecha, turno, tipo de máquina y máquina en los selectores. "
                "Para descargar: menú de cada panel › Inspect › Data › Download CSV (activar «Download for Excel»). "
                "Los datos para descargar (sección plegable al final) usan «Descarga: máquinas» y «Descarga: periodo», "
                "contado desde la fecha del turno elegida.")
TABLE = 1
TYPES = ["DI", "STANDUM", "PRINTER", "ISPRAY", "MINSTER"]

# colours readable on both dark and light themes
BLUE, RED, PURPLE, ORANGE, GREY, GREEN, YELLOW = "#5794F2", "#F2495C", "#B877D9", "#FF9830", "#8E8E8E", "#73BF69", "#FADE2A"

# ------------------------------------------------------------------ capacity per machine (gauge maximum)
spec = importlib.util.spec_from_file_location("hpr_config", HERE.parent / "functions" / "hourly_production_report" / "config.py")
HC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HC)
DEFAULT_RATE = 16000.0   # D&I / STANDUM have no nominal_capacity: ~ the highest observed rate (190k per shift)
CAP_CASE = "CASE '${maquina}' " + " ".join(
    f"WHEN '{c['code'].lower()}' THEN {int((c.get('nominal_capacity') or DEFAULT_RATE) * 12)}"
    for c in HC.MACHINE_CONFIGS) + f" ELSE {int(DEFAULT_RATE * 12)} END"

# ------------------------------------------------------------------ per machine type (hidden variables)
H = 'hour_label AS "Hora"'
OBS = 'observations AS "Observaciones / Incidencias"'
EFF = 'efficiency_pct AS "% Eficiencia"'
DOWN = 'downtime_min AS "Tiempo parada (min)"'
PER_TYPE = {
    # table columns (as the Streamlit Reporte shows each type)
    "cols": {
        "DI": [H, 'production AS "PROD. LATAS"', 'short_cans AS "LAT CORTAS"', 'trimmer_jams AS "TRANC TRIMMER"',
               'cans_by_short_can AS "LAT x LAT CORTAS"', 'cans_by_trimmer_jam AS "LAT x TRANC TRIM"',
               'downtime_by_short_can_min AS "Parada x lat cortas (min)"',
               'downtime_by_trimmer_jam_min AS "Parada x tranc trim (min)"', DOWN, 'scrap_kg AS "Merma (kg)"',
               'scrap_pct AS "% Merma"', EFF, OBS],
        "PRINTER": [H, 'production AS "Producción x hora"', 'retrac AS "Retrac x hora"', 'blow_off AS "Blow off"',
                    DOWN, EFF, OBS],
        "ISPRAY": [H, 'production AS "Producción x hora"', DOWN, EFF, OBS],
        "MINSTER": [H, 'golpes_bobina AS "Golpes bobina"', 'golpes_turno AS "Golpes turno"', DOWN, EFF, OBS],
    },
    # second chart: (title, select list)
    "chart2": {
        "DI": ("Merma por hora", 'trimmer_jams AS "Tranc. trimmer", short_cans AS "Latas cortas"'),
        "PRINTER": ("Retrac y blow off por hora", 'retrac AS "Retrac", blow_off AS "Blow off"'),
        "ISPRAY": ("Tiempo de parada por hora (min)", 'downtime_min AS "Tiempo parada (min)"'),
        "MINSTER": ("Tiempo de parada por hora (min)", 'downtime_min AS "Tiempo parada (min)"'),
    },
    # gauges 2 and 3: (title, value expression, max)
    "g2": {
        "DI": ("Latas cortas total", "sum(short_cans)", 50),
        "PRINTER": ("Retrac total", "sum(retrac)", 1500),
        "ISPRAY": ("Eficiencia promedio (%)", "round(avg(efficiency_pct) FILTER (WHERE production > 0), 1)", 100),
        # MINSTER production IS its strokes per hour, so a strokes gauge would repeat gauge 1
        "MINSTER": ("Horas con producción", "count_if(production > 0)", 12),
    },
    "g3": {
        "DI": ("Trancamientos trimmer", "sum(trimmer_jams)", 50),
        "PRINTER": ("Blow off total", "sum(blow_off)", 20000),
        "ISPRAY": ("Horas con producción", "count_if(production > 0)", 12),
        "MINSTER": ("Eficiencia promedio (%)", "round(avg(efficiency_pct) FILTER (WHERE production > 0), 1)", 100),
    },
}
for part in PER_TYPE.values():
    part["STANDUM"] = part["DI"]


def sql_str(s):
    return "'" + str(s).replace("'", "''") + "'"


def case(values):
    """CASE '${tipo}' WHEN 'DI' THEN '...' ... END  (string literal per type)."""
    return "CASE '${tipo}' " + " ".join(f"WHEN '{t}' THEN {sql_str(values[t])}" for t in TYPES) + " END"


def target(sql, ref="A", hide=False):
    t = {"refId": ref, "datasource": DS, "format": TABLE, "rawSQL": sql, "connectionArgs": CONN}
    if hide:
        t["hide"] = False   # config queries must run; panels only DISPLAY ref A (see reduceOptions.fields)
    return t


def var_query(name, label, sql, multi=False, include_all=False, hide=0):
    return {"type": "query", "name": name, "label": label, "datasource": DS, "definition": sql,
            "query": {"rawSQL": sql, "format": TABLE, "connectionArgs": CONN}, "refresh": 1, "sort": 0,
            "multi": multi, "includeAll": include_all, "hide": hide, "current": {}, "options": []}


panels = []
_id = [0]


def panel(kind, title, grid, targets, **extra):
    _id[0] += 1
    p = {"id": _id[0], "type": kind, "title": title, "gridPos": dict(zip("xywh", grid)), "datasource": DS,
         "targets": targets}
    p.update(extra)
    panels.append(p)
    return p


def thresholds(steps, mode="absolute"):
    return {"mode": mode, "steps": [{"color": c, "value": v} for c, v in steps]}


CONFIG_FROM_B = {"id": "configFromData", "options": {"configRefId": "B", "mappings": [
    {"fieldName": "max", "handlerKey": "max"}, {"fieldName": "min", "handlerKey": "min"}]}}

# ------------------------------------------------------------------ header
panel("text", "", (0, 0, 24, 2), [],         # h=1 clips the line
      options={"mode": "markdown",
               "content": "Elija fecha, turno, tipo de máquina y máquina en los selectores. Para descargar datos: "
                          "menú de cada panel › **Inspect › Data › Download CSV** (activar «Download for Excel»). "
                          "La sección **Datos para descargar**, al final, usa «Descarga: máquinas» y "
                          "«Descarga: periodo» (contado desde la fecha del turno elegida)."},
      transparent=True, datasource=None)
panels[-1].pop("targets")
panels[-1].pop("datasource")

# ------------------------------------------------------------------ charts
BAR_OPTS = {"xField": "Hora", "showValue": "always", "xTickLabelRotation": -45, "barWidth": 0.8, "groupWidth": 0.7,
            "legend": {"showLegend": False}, "tooltip": {"mode": "multi"}}
panel("barchart", "Producción por hora · ${maquina} · ${fecha} ${turno:text}", (0, 2, 12, 9),
      [target(f'SELECT hour_label AS "Hora", production AS "Producción" {SHIFT} ORDER BY slot')],
      options=BAR_OPTS,
      fieldConfig={"defaults": {"color": {"mode": "fixed", "fixedColor": BLUE}, "unit": "locale", "decimals": 0,
                                "custom": {"fillOpacity": 85, "gradientMode": "none", "lineWidth": 0}},
                   "overrides": []})
panel("barchart", "${chart2_title} · ${maquina}", (12, 2, 12, 9),
      [target(f'SELECT hour_label AS "Hora", ${{chart2:raw}} {SHIFT} ORDER BY slot')],
      options={**BAR_OPTS, "stacking": "normal", "showValue": "auto",
               "legend": {"showLegend": True, "placement": "bottom", "displayMode": "list"}},
      fieldConfig={"defaults": {"unit": "locale", "decimals": 0,
                                "custom": {"fillOpacity": 85, "gradientMode": "none", "lineWidth": 0}},
                   "overrides": [
                       {"matcher": {"id": "byName", "options": n},
                        "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
                       for n, c in (("Tranc. trimmer", PURPLE), ("Latas cortas", RED), ("Retrac", ORANGE),
                                    ("Blow off", RED), ("Tiempo parada (min)", GREY))]})

# ------------------------------------------------------------------ gauges (value = ref A, min/max = ref B)
GAUGE_OPTS = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/^Valor$/", "values": False},
              "showThresholdMarkers": True, "showThresholdLabels": False, "minVizHeight": 75, "minVizWidth": 75}


def gauge(title, x, value_sql, max_sql, unit, color_cfg, thr, description=""):
    panel("gauge", title, (x, 11, 6, 7),
          [target(f'SELECT coalesce({value_sql}, 0) AS "Valor" {SHIFT}'),
           target(f"SELECT 0 AS min, {max_sql} AS max", ref="B", hide=True)],
          options=GAUGE_OPTS, transformations=[CONFIG_FROM_B], description=description,
          fieldConfig={"defaults": {"unit": unit, "decimals": 0, "color": color_cfg, "thresholds": thr},
                       "overrides": []})


gauge("Producción total (latas)", 0, "sum(production)", CAP_CASE, "locale",
      {"mode": "thresholds"}, thresholds([(RED, None), (YELLOW, 50), (GREEN, 80)], mode="percentage"),
      description="Máximo del indicador = capacidad nominal de la máquina × 12 horas (D&I y STANDUM: 16.000 latas/h, "
                  "sin capacidad nominal configurada). Rojo < 50 %, amarillo 50–80 %, verde ≥ 80 % de ese máximo.")
for i, g in ((1, "g2"), (2, "g3")):
    gauge(f"${{{g}_title}}", i * 6, f"${{{g}:raw}}", case({t: PER_TYPE[g][t][2] for t in TYPES}), "locale",
          {"mode": "fixed", "fixedColor": PURPLE if g == "g3" else RED}, thresholds([(PURPLE, None)]))
gauge("Tiempo de parada total", 18, "sum(downtime_min)", "720", "suffix: min",
      {"mode": "thresholds"}, thresholds([(GREEN, None), (YELLOW, 120), (RED, 300)]),
      description="Minutos de parada en el turno, sobre 720 (12 h). Verde < 2 h, amarillo < 5 h, rojo ≥ 5 h.")

# ------------------------------------------------------------------ hourly table
OBS_MAPPINGS = [
    {"type": "regex", "options": {"pattern": "^Sin producción.*", "result": {"color": GREY, "index": 0}}},
    {"type": "regex", "options": {"pattern": "^(Operación (normal|estándar)).*", "result": {"color": GREEN, "index": 1}}},
    {"type": "regex", "options": {"pattern": "^Parada por.*", "result": {"color": YELLOW, "index": 2}}},
    {"type": "regex", "options": {"pattern": ".+", "result": {"color": ORANGE, "index": 3}}},   # plant incidents
]
EFF_OVERRIDE = {"matcher": {"id": "byRegexp", "options": "^% Eficiencia"}, "properties": [
    {"id": "unit", "value": "percent"}, {"id": "decimals", "value": 1},
    {"id": "custom.cellOptions", "value": {"type": "color-text"}},
    {"id": "thresholds", "value": thresholds([(RED, None), (YELLOW, 50), (GREEN, 80)])},
    {"id": "color", "value": {"mode": "thresholds"}}]}
TABLE_OVERRIDES = [
    EFF_OVERRIDE,
    {"matcher": {"id": "byName", "options": "% Merma"}, "properties": [{"id": "unit", "value": "percent"},
                                                                       {"id": "decimals", "value": 2}]},
    {"matcher": {"id": "byName", "options": "Merma (kg)"}, "properties": [{"id": "unit", "value": "none"},
                                                                          {"id": "decimals", "value": 2}]},
    {"matcher": {"id": "byRegexp", "options": "^Observaciones"}, "properties": [
        {"id": "custom.width", "value": 330}, {"id": "mappings", "value": OBS_MAPPINGS},
        {"id": "custom.cellOptions", "value": {"type": "color-text"}}]},
    {"matcher": {"id": "byName", "options": "Hora"}, "properties": [{"id": "custom.width", "value": 110}]},
]
panel("table", "Detalle horario del turno · ${maquina} · ${fecha} ${turno:text}", (0, 18, 24, 12),
      [target(f"SELECT ${{cols:raw}} {SHIFT} ORDER BY slot")],
      options={"showHeader": True, "cellHeight": "sm", "footer": {"show": True, "reducer": ["sum"],
                                                                  "countRows": False, "fields": ""}},
      fieldConfig={"defaults": {"unit": "locale", "decimals": 0, "custom": {"align": "auto", "filterable": False}},
                   "overrides": TABLE_OVERRIDES},
      description="Columnas según el tipo de máquina, como en el Reporte de Streamlit. Fila de totales al pie. "
                  "Observaciones: naranja = incidencia registrada en planta, amarillo = parada automática, "
                  "gris = sin producción. Descargar: menú del panel › Inspect › Data › Download CSV.")

# ------------------------------------------------------------------ download (collapsed row)
SHIFT_LABEL = "CASE shift WHEN 'day' THEN '6AM-6PM' ELSE '6PM-6AM' END"
# hour_start_local already IS plant time: sent as text, or Grafana takes the timestamp as UTC and shifts it another -4 h
DL_COLS = (f'shift_date AS "Fecha turno", {SHIFT_LABEL} AS "Turno", '
           "date_format(hour_start_local, '%Y-%m-%d %H:%i') AS \"Hora inicio (planta)\", "
           'hour_label AS "Hora", line AS "Línea", machine_type AS "Tipo", machine AS "Máquina", '
           'production AS "Producción", short_cans AS "Latas cortas", trimmer_jams AS "Tranc. trimmer", '
           'scrap_kg AS "Merma (kg)", scrap_pct AS "% Merma", efficiency_pct AS "% Eficiencia", '
           'downtime_min AS "Tiempo parada (min)", retrac AS "Retrac", blow_off AS "Blow off", '
           'golpes_bobina AS "Golpes bobina", golpes_turno AS "Golpes turno", observations AS "Observaciones"')
TOT = (f'shift_date AS "Fecha turno", {SHIFT_LABEL} AS "Turno", line AS "Línea", machine_type AS "Tipo", '
       'machine AS "Máquina", '
       'count(*) AS "Horas", sum(production) AS "Producción", sum(short_cans) AS "Latas cortas", '
       'sum(trimmer_jams) AS "Tranc. trimmer", round(sum(scrap_kg), 2) AS "Merma (kg)", '
       'round(avg(efficiency_pct) FILTER (WHERE production > 0), 2) AS "% Eficiencia (horas activas)", '
       'sum(downtime_min) AS "Tiempo parada (min)", sum(retrac) AS "Retrac", sum(blow_off) AS "Blow off"')
dl_panels_start = len(panels)
panel("table", "Detalle por hora (una fila por máquina y hora)", (0, 31, 24, 12),
      [target(f"SELECT {DL_COLS} FROM {T} WHERE {RANGE} ORDER BY hour_start_utc, machine LIMIT 50000")],
      options={"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
      fieldConfig={"defaults": {"unit": "locale", "decimals": 0, "noValue": "—", "custom": {"filterable": True}},
                   "overrides": TABLE_OVERRIDES[:3]},
      description="Periodo: «Descarga: periodo», contado desde la fecha del turno elegida. Máquinas: «Descarga: máquinas». "
                  "Descargar: menú del panel › Inspect › Data › Download CSV (activar «Download for Excel»). "
                  "Máximo 50.000 filas: para rangos largos, filtrar máquinas.")
panel("table", "Totales por turno y máquina", (0, 43, 24, 10),
      [target(f"SELECT {TOT} FROM {T} WHERE {RANGE} GROUP BY shift_date, shift, line, machine_type, machine "
              f"ORDER BY shift_date, shift, line, machine_type, machine")],
      options={"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
      fieldConfig={"defaults": {"unit": "locale", "decimals": 0, "noValue": "—", "custom": {"filterable": True}},
                   "overrides": TABLE_OVERRIDES[:3]},
      description="Descargar: menú del panel › Inspect › Data › Download CSV.")
dl_panels = panels[dl_panels_start:]
del panels[dl_panels_start:]
panels.append({"id": 100, "type": "row", "collapsed": True, "gridPos": {"x": 0, "y": 30, "w": 24, "h": 1},
               "title": "Datos para descargar · «Descarga: máquinas» y «Descarga: periodo»",
               "panels": dl_panels})

# ------------------------------------------------------------------ variables
RECENT = "shift_date >= date_format(current_date - interval '90' day, '%Y-%m-%d')"


def type_var(name, values_by_type):
    """Hidden variable whose single value is the text for the selected type (a SQL fragment or a panel title).
    The Athena plugin ignores __text/__value columns (text = value = first column), so titles get their own variables
    (<name>_title) instead of ${name:text}."""
    return var_query(name, name, f'SELECT {case(values_by_type)} AS "v"', hide=2)


variables = [
    # Only an Athena data source whose NAME contains "Polar" (e.g. "Athena - Polar produccion"): the workspace may hold
    # other Athena data sources (other clients, or an unconfigured duplicate) and Grafana would otherwise take the
    # first one alphabetically.
    {"type": "datasource", "name": "ds", "label": "Fuente de datos", "query": "grafana-athena-datasource",
     "regex": "/[Pp]olar/", "hide": 2, "current": {}, "options": [], "refresh": 1},
    var_query("fecha", "Fecha del turno",
              f"SELECT DISTINCT shift_date FROM {T} WHERE {RECENT} ORDER BY shift_date DESC"),
    {"type": "custom", "name": "turno", "label": "Turno", "query": "6AM-6PM : day, 6PM-6AM : night",
     "current": {"text": "6AM-6PM", "value": "day"}, "multi": False, "includeAll": False, "hide": 0,
     "options": [{"text": "6AM-6PM", "value": "day", "selected": True},
                 {"text": "6PM-6AM", "value": "night", "selected": False}]},
    {"type": "custom", "name": "tipo", "label": "Tipo de máquina",
     "query": "MINSTER : MINSTER, D&I : DI, STANDUM : STANDUM, PRINTER : PRINTER, ISPRAY : ISPRAY",
     "current": {"text": "STANDUM", "value": "STANDUM"}, "multi": False, "includeAll": False, "hide": 0,
     "options": [{"text": t, "value": v, "selected": v == "STANDUM"} for t, v in
                 (("MINSTER", "MINSTER"), ("D&I", "DI"), ("STANDUM", "STANDUM"), ("PRINTER", "PRINTER"),
                  ("ISPRAY", "ISPRAY"))]},
    var_query("maquina", "Máquina",
              f"SELECT DISTINCT machine FROM {T} WHERE {RECENT} AND machine_type = '${{tipo}}' ORDER BY machine"),
    var_query("descarga", "Descarga: máquinas",
              f"SELECT DISTINCT machine FROM {T} WHERE {RECENT} ORDER BY machine", multi=True, include_all=True),
    {"type": "custom", "name": "periodo", "label": "Descarga: periodo",
     "query": ", ".join(f"{t} : {v}" for t, v in PERIODS),
     "current": {"text": PERIODS[0][0], "value": PERIODS[0][1]}, "multi": False, "includeAll": False, "hide": 0,
     "options": [{"text": t, "value": v, "selected": i == 0} for i, (t, v) in enumerate(PERIODS)]},
    type_var("cols", {t: ", ".join(PER_TYPE["cols"][t]) for t in TYPES}),
    type_var("chart2", {t: PER_TYPE["chart2"][t][1] for t in TYPES}),
    type_var("chart2_title", {t: PER_TYPE["chart2"][t][0] for t in TYPES}),
    type_var("g2", {t: PER_TYPE["g2"][t][1] for t in TYPES}),
    type_var("g2_title", {t: PER_TYPE["g2"][t][0] for t in TYPES}),
    type_var("g3", {t: PER_TYPE["g3"][t][1] for t in TYPES}),
    type_var("g3_title", {t: PER_TYPE["g3"][t][0] for t in TYPES}),
]
for v in variables:
    if v.get("allValue", 1) is None:
        v.pop("allValue")

dashboard = {
    "title": "Reporte de Producción · Superenvases",
    "uid": "polar-reporte-produccion",
    "description": INSTRUCTIONS,
    "tags": ["empresas-polar", "produccion"],
    "timezone": "America/Caracas",
    "editable": True,
    "graphTooltip": 1,
    "time": {"from": "now-7d/d", "to": "now"},
    "timepicker": {"hidden": True},          # every query filters by the shift-date / period selectors instead
    "refresh": "",
    "schemaVersion": 39,
    "templating": {"list": variables},
    "panels": panels,
    "annotations": {"list": []},
    # every other dashboard tagged empresas-polar (e.g. the Dashboard General), as header links
    "links": [{"type": "dashboards", "title": "Dashboards Polar", "tags": ["empresas-polar"], "asDropdown": False,
               "includeVars": False, "keepTime": False, "targetBlank": False, "icon": "dashboard"}],
}
out = HERE / "dashboard_produccion_athena.json"
out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {out.name}: {len(panels)} top-level panels (+{len(dl_panels)} in the download row), "
      f"{len(variables)} variables")

if "--sql" in sys.argv:
    import tempfile
    qdir = Path(tempfile.gettempdir()) / "dashboard_produccion_athena_sql"
    qdir.mkdir(exist_ok=True)
    for f in qdir.glob("*.sql"):
        f.unlink()
    machine_by_type = {"DI": "di11", "STANDUM": "standum32", "PRINTER": "p11", "ISPRAY": "ispray12",
                       "MINSTER": "minster_l1"}
    n = 0
    for t in TYPES:
        def vval(name, text=False):
            part = PER_TYPE[name][t]
            if name == "cols":
                return ", ".join(part)
            return part[0] if text else part[1]
        sample = {"${fecha}": "2026-11-18", "${turno}": "day", "${maquina}": machine_by_type[t], "${tipo}": t,
                  "${descarga:singlequote}": "'standum32','di11','p11','minster_l1'", "${periodo}": "__PERIODO__"}
        for name in ("cols", "chart2", "g2", "g3"):
            sample[f"${{{name}:raw}}"] = vval(name)
        all_panels = panels + dl_panels
        queries = [(p["title"], tg["rawSQL"], tg["refId"]) for p in all_panels if p.get("targets") for tg in p["targets"]]
        if t == "DI":      # type-independent queries once
            queries += [(f"variable {v['name']}", v["definition"], "V") for v in variables if v["type"] == "query"]
        for title, sql, ref in queries:
            if t != "DI" and ("Descarga" in title or "Detalle por hora" in title or "Totales" in title):
                continue
            for k, v in sample.items():
                sql = sql.replace(k, v)
            for k in ("${g2_title}", "${g3_title}", "${chart2_title}"):
                title = title.replace(k, vval(k[2:k.index("_title")], text=True))
            (qdir / f"{t}_{n:02d}{ref}.sql").write_text(f"-- [{t}] {title}\n{sql}\n", encoding="utf-8")
            n += 1
    print(f"{n} test queries in {qdir}")
