"""Builds grafana/dashboard_general_athena.json: the Streamlit "Dashboard General de Producción" (overview_dashboard/)
in Grafana, from the same Athena table as the Reporte (polar_production.production_hourly, fed by
functions/production_reports_to_s3).

Same numbers as overview_dashboard/main.py, for the selected shift date + shift:
  - Eficiencia global / por línea: average % efficiency over the hours WITH production;
  - Máquinas activas: machines whose LAST reported hour has production > 0, out of the 32 configured;
  - Tiempo de parada total: sum of downtime minutes;
  - Eventos de merma: short cans + trimmer jams + retrac + blow off;
  - per line: efficiency gauge (target 85 %), production per machine type in flow order, machine status from the last
    reported hour (Operando: production > 0; Falla: "falla" in the observations; Detenida; Sin datos: no hours).

    python grafana/make_dashboard_general_athena.py          # writes the JSON
    python grafana/make_dashboard_general_athena.py --sql    # also writes the queries with sample values to
                                                             # %TEMP%/dashboard_general_athena_sql, for Athena
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
T = "polar_production.production_hourly"
DS = {"type": "grafana-athena-datasource", "uid": "${ds}"}
# "__default": use the data source's own region/catalog/database/workgroup (explicit values drop the workgroup).
CONN = {"region": "__default", "catalog": "__default", "database": "__default",
        "resultReuseEnabled": False, "resultReuseMaxAgeInMinutes": 60}
TABLE = 1
SHIFT = "shift_date = '${fecha}' AND shift = '${turno}'"
TARGET_PCT = 85

BLUE, RED, ORANGE, GREY, GREEN, YELLOW = "#5794F2", "#F2495C", "#FF9830", "#8E8E8E", "#73BF69", "#FADE2A"
# overview_dashboard/config.py TYPE_COLORS / STATUS_COLORS, except D&I: its #002B49 is invisible on Grafana's dark theme.
# Status panels: reduceOptions.fields must stay "" (numeric fields): a name regex is matched against the DISPLAY name,
# which displayName turns into the machine code, so it matched nothing ("No data").
TYPE_COLORS = {"MINSTER": "#0284c7", "DI": "#5B7FA6", "STANDUM": "#475569", "PRINTER": "#0078D4", "ISPRAY": "#10b981"}
TYPE_LABELS = {"MINSTER": "Minster", "DI": "D&I", "STANDUM": "Standum", "PRINTER": "Printer", "ISPRAY": "ISpray"}
STATUS = [(0, "Sin datos", "#9ca3af"), (1, "Operando", "#16a34a"), (2, "Detenida", "#d97706"), (3, "Falla", "#dc2626")]
LINES = {"L1": ("Línea 1", ["MINSTER", "DI", "PRINTER", "ISPRAY"]),
         "L3": ("Línea 3", ["MINSTER", "STANDUM", "PRINTER", "ISPRAY"])}

# ------------------------------------------------------------------ machine roster (same copy the S3 function uses)
spec = importlib.util.spec_from_file_location(
    "s3_config", HERE.parent / "functions" / "production_reports_to_s3" / "config.py")
S3C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S3C)
ROSTER = []          # (code, line, type, order): flow order within the line, then code
for line, (_, flow) in LINES.items():
    for mtype in flow:
        for code in sorted(c for c, (l, t) in S3C.MACHINES.items() if l == line and t == mtype):
            ROSTER.append((code, line, mtype, len(ROSTER)))
N_MACHINES = len(ROSTER)
ROSTER_SQL = "m(machine, line, ord) AS (VALUES " + ", ".join(f"('{c}', '{l}', {o})" for c, l, _, o in ROSTER) + ")"
# last reported hour per machine (Streamlit: sort by entry slot, take the last)
LAST = (f"d AS (SELECT machine, max_by(production, slot) AS p, max_by(observations, slot) AS o "
        f"FROM {T} WHERE {SHIFT} GROUP BY machine)")
SCRAP = "coalesce(short_cans, 0) + coalesce(trimmer_jams, 0) + coalesce(retrac, 0) + coalesce(blow_off, 0)"
EFF = "round(avg(efficiency_pct) FILTER (WHERE production > 0), 1)"


def target(sql, ref="A"):
    return {"refId": ref, "datasource": DS, "format": TABLE, "rawSQL": sql, "connectionArgs": CONN}


def thresholds(steps):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in steps]}


EFF_THR = thresholds([(RED, None), (YELLOW, 50), (GREEN, TARGET_PCT)])
panels = []


def panel(kind, title, grid, sql, **extra):
    p = {"id": len(panels) + 1, "type": kind, "title": title, "gridPos": dict(zip("xywh", grid)), "datasource": DS,
         "targets": [target(sql)]}
    p.update(extra)
    panels.append(p)
    return p


def stat(title, x, sql, unit, decimals, color, description=""):
    panel("stat", title, (x, 0, 6, 4), sql, description=description,
          options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/", "values": False},
                   "colorMode": "value", "graphMode": "none", "textMode": "value", "justifyMode": "auto",
                   "orientation": "auto", "showPercentChange": False},
          fieldConfig={"defaults": {"unit": unit, "decimals": decimals, "noValue": "—", "color": color,
                                    "thresholds": EFF_THR}, "overrides": []})


# ------------------------------------------------------------------ KPIs (both lines)
stat("Eficiencia Global", 0, f'SELECT {EFF} AS "Eficiencia" FROM {T} WHERE {SHIFT}', "percent", 1,
     {"mode": "thresholds"},
     description=f"Promedio del % de eficiencia en las horas con producción, todas las máquinas. Meta: {TARGET_PCT} %.")
stat("Máquinas Activas", 6,
     f"WITH {LAST} SELECT concat(cast(count_if(p > 0) AS varchar), ' / {N_MACHINES}') AS \"Activas\" FROM d",
     "string", None, {"mode": "fixed", "fixedColor": "text"},
     description="Máquinas cuya última hora reportada del turno tiene producción.")
stat("Tiempo de Parada Total", 12, f'SELECT sum(downtime_min) AS "Parada" FROM {T} WHERE {SHIFT}',
     "suffix: min", 0, {"mode": "fixed", "fixedColor": "text"},
     description="Suma de los minutos de parada de todas las máquinas en el turno.")
stat("Eventos de Merma", 18, f'SELECT sum({SCRAP}) AS "Merma" FROM {T} WHERE {SHIFT}', "locale", 0,
     {"mode": "fixed", "fixedColor": "text"},
     description="Latas cortas + trancamientos de trimmer (D&I / Standum) + retrac + blow off (Printer).")

# ------------------------------------------------------------------ one column per line
for i, (line, (name, flow)) in enumerate(LINES.items()):
    x = i * 12
    n = sum(1 for _, l, _, _ in ROSTER if l == line)
    panel("gauge", f"Eficiencia {name}", (x, 4, 4, 8),
          f'SELECT {EFF} AS "Eficiencia" FROM {T} WHERE {SHIFT} AND line = \'{line}\'',
          description=f"Promedio del % de eficiencia en las horas con producción de {name}. "
                      f"Rojo < 50 %, amarillo 50–{TARGET_PCT} %, verde ≥ {TARGET_PCT} % (meta).",
          options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                   "showThresholdMarkers": True, "showThresholdLabels": False, "minVizHeight": 75, "minVizWidth": 75},
          fieldConfig={"defaults": {"unit": "percent", "decimals": 1, "min": 0, "max": 100, "noValue": "—",
                                    "color": {"mode": "thresholds"}, "thresholds": EFF_THR}, "overrides": []})
    # one row, one column per machine type (flow order): each bar gets its own colour and legend entry
    cols = ", ".join(f"coalesce(sum(production) FILTER (WHERE machine_type = '{t}'), 0) AS \"{TYPE_LABELS[t]}\""
                     for t in flow)
    panel("barchart", f"{name} · Producción por tipo de máquina", (x + 4, 4, 8, 8),
          f"SELECT 'Producción' AS \"x\", {cols} FROM {T} WHERE {SHIFT} AND line = '{line}'",
          description=f"{n} máquinas · " + " → ".join(TYPE_LABELS[t] for t in flow) +
                      ". Producción del turno por tipo (Minster: golpes).",
          options={"xField": "x", "showValue": "always", "orientation": "vertical", "barWidth": 0.9,
                   "groupWidth": 0.8, "xTickLabelRotation": 0, "stacking": "none",
                   "legend": {"showLegend": True, "placement": "bottom", "displayMode": "list"},
                   "tooltip": {"mode": "multi"}},
          fieldConfig={"defaults": {"unit": "short", "decimals": 0,
                                    "custom": {"fillOpacity": 90, "gradientMode": "none", "lineWidth": 0,
                                               "axisPlacement": "hidden"}},
                       "overrides": [{"matcher": {"id": "byName", "options": TYPE_LABELS[t]},
                                      "properties": [{"id": "color", "value": {"mode": "fixed",
                                                                                "fixedColor": TYPE_COLORS[t]}}]}
                                     for t in flow]})
    panel("stat", f"{name} · Estado de máquinas ({n})", (x, 12, 12, 8),
          f"WITH {ROSTER_SQL}, {LAST} "
          f"SELECT upper(m.machine) AS maquina, CASE WHEN d.machine IS NULL THEN 0 WHEN d.p > 0 THEN 1 "
          f"WHEN lower(coalesce(d.o, '')) LIKE '%falla%' THEN 3 ELSE 2 END AS estado "
          f"FROM m LEFT JOIN d ON d.machine = m.machine WHERE m.line = '{line}' ORDER BY m.ord",
          description="Según la última hora reportada del turno: Operando = con producción; Falla = «falla» en las "
                      "observaciones; Detenida = sin producción; Sin datos = ninguna hora reportada.",
          options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": True},
                   # colour only the status text (a coloured background was too loud with 24+ green machines)
                   "colorMode": "value", "graphMode": "none", "textMode": "value_and_name",
                   "justifyMode": "center", "orientation": "auto", "showPercentChange": False,
                   "text": {"titleSize": 13, "valueSize": 12}},
          fieldConfig={"defaults": {"displayName": "${__data.fields.maquina}", "color": {"mode": "fixed"},
                                    "mappings": [{"type": "value", "options": {
                                        str(v): {"text": t, "color": c, "index": v} for v, t, c in STATUS}}]},
                       "overrides": []})

# ------------------------------------------------------------------ variables
RECENT = "shift_date >= date_format(current_date - interval '90' day, '%Y-%m-%d')"
variables = [
    {"type": "datasource", "name": "ds", "label": "Fuente de datos", "query": "grafana-athena-datasource",
     "regex": "/[Pp]olar/", "hide": 2, "current": {}, "options": [], "refresh": 1},
    {"type": "query", "name": "fecha", "label": "Fecha del turno", "datasource": DS,
     "definition": f"SELECT DISTINCT shift_date FROM {T} WHERE {RECENT} ORDER BY shift_date DESC",
     "query": {"rawSQL": f"SELECT DISTINCT shift_date FROM {T} WHERE {RECENT} ORDER BY shift_date DESC",
               "format": TABLE, "connectionArgs": CONN},
     "refresh": 1, "sort": 0, "multi": False, "includeAll": False, "hide": 0, "current": {}, "options": []},
    {"type": "custom", "name": "turno", "label": "Turno", "query": "6AM-6PM : day, 6PM-6AM : night",
     "current": {"text": "6AM-6PM", "value": "day"}, "multi": False, "includeAll": False, "hide": 0,
     "options": [{"text": "6AM-6PM", "value": "day", "selected": True},
                 {"text": "6PM-6AM", "value": "night", "selected": False}]},
]

dashboard = {
    "title": "Dashboard General · Superenvases",
    "uid": "polar-dashboard-general",
    "description": "Todas las máquinas · Línea 1 y Línea 3. Elija fecha y turno en los selectores.",
    "tags": ["empresas-polar", "produccion"],
    "timezone": "America/Caracas",
    "editable": True,
    "graphTooltip": 0,
    "time": {"from": "now-24h", "to": "now"},
    "timepicker": {"hidden": True},          # every query filters by the shift date / shift selectors
    "refresh": "15m",                        # S3 is refreshed every 15 min by production_reports_to_s3
    "schemaVersion": 39,
    "templating": {"list": variables},
    "panels": panels,
    "annotations": {"list": []},
    "links": [{"type": "dashboards", "title": "Reporte de Producción", "tags": ["empresas-polar"],
               "asDropdown": False, "includeVars": False, "keepTime": False, "targetBlank": False, "icon": "dashboard"}],
}
out = HERE / "dashboard_general_athena.json"
out.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {out.name}: {len(panels)} panels, {N_MACHINES} machines")

if "--sql" in sys.argv:
    import tempfile
    qdir = Path(tempfile.gettempdir()) / "dashboard_general_athena_sql"
    qdir.mkdir(exist_ok=True)
    for f in qdir.glob("*.sql"):
        f.unlink()
    sample = {"${fecha}": sys.argv[sys.argv.index("--sql") + 1] if len(sys.argv) > sys.argv.index("--sql") + 1
              else "2026-11-24", "${turno}": "day"}
    for i, p in enumerate(panels):
        sql = p["targets"][0]["rawSQL"]
        for k, v in sample.items():
            sql = sql.replace(k, v)
        (qdir / f"{i:02d}.sql").write_text(f"-- {p['title']}\n{sql}\n", encoding="utf-8")
    print(f"{len(panels)} test queries in {qdir}")
