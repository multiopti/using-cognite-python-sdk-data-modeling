"""Configuration for production_reports_to_s3 (hourly Production Report events -> S3 -> Athena -> Grafana).

MACHINES is a COPY of functions/hourly_production_report/config.py MACHINE_CONFIGS (code -> line, machine type):
Cognite Functions can't import code from other folders. test_handler.py checks it still matches.
"""
from datetime import timedelta, timezone

BUCKET = "ingedaca-polar-production-data"     # private: all public access blocked, SSE-S3, versioning on
PREFIX = "production_hourly"                  # s3://BUCKET/PREFIX/shift_date=YYYY-MM-DD/shift=day|night/<code>.jsonl
AWS_REGION = "us-east-1"

EVENT_TYPE = "Production Report"
LOCAL_TZ = timezone(timedelta(hours=-4))      # plant time (UTC-4, no DST), as in hourly_production_report

# Scheduled run (every 15 min): rewrite the shifts of every event created/updated in the last LOOKBACK_HOURS. It
# overlaps several runs, so a failed run is covered by the next one; hourly_production_report, shift_reconciler and
# plant_incident_sync updates are all picked up this way.
LOOKBACK_HOURS = 3

MACHINES = {
    "p11": ("L1", "PRINTER"), "p31": ("L3", "PRINTER"), "p32": ("L3", "PRINTER"),
    "di11": ("L1", "DI"), "di12": ("L1", "DI"), "di14": ("L1", "DI"), "di15": ("L1", "DI"), "di17": ("L1", "DI"),
    "di18": ("L1", "DI"),
    "standum31": ("L3", "STANDUM"), "standum32": ("L3", "STANDUM"), "standum33": ("L3", "STANDUM"),
    "standum34": ("L3", "STANDUM"), "standum35": ("L3", "STANDUM"), "standum36": ("L3", "STANDUM"),
    "standum37": ("L3", "STANDUM"), "standum38": ("L3", "STANDUM"),
    "minster_l1": ("L1", "MINSTER"), "minster_l3": ("L3", "MINSTER"),
    "ispray11": ("L1", "ISPRAY"), "ispray12": ("L1", "ISPRAY"), "ispray13": ("L1", "ISPRAY"),
    "ispray14": ("L1", "ISPRAY"), "ispray15": ("L1", "ISPRAY"),
    "ispray31": ("L3", "ISPRAY"), "ispray32": ("L3", "ISPRAY"), "ispray33": ("L3", "ISPRAY"),
    "ispray34": ("L3", "ISPRAY"), "ispray35": ("L3", "ISPRAY"), "ispray36": ("L3", "ISPRAY"),
    "ispray37": ("L3", "ISPRAY"), "ispray38": ("L3", "ISPRAY"),
}

# Output column -> event metadata keys to try, in order (same keys the Fusion/plant Reporte reads). A column that
# doesn't apply to a machine type is null in that machine's rows.
NUMERIC_FIELDS = {
    "production": ["hourly_production"],
    "short_cans": ["short_cans_per_hour"],
    "trimmer_jams": ["trimmer_jams_per_hour"],
    "cans_by_short_can": ["cans_by_short_can"],
    "cans_by_trimmer_jam": ["cans_by_trimmer_jam"],
    "downtime_by_short_can_min": ["downtime_by_short_can_min"],
    "downtime_by_trimmer_jam_min": ["downtime_by_trimmer_jam_min"],
    "downtime_min": ["total_downtime_min", "downtime_minutes"],
    "scrap_kg": ["merma_kg"],
    "scrap_pct": ["pct_merma"],
    "efficiency_pct": ["pct_eficiencia", "efficiency"],
    "retrac": ["hourly_retrac"],
    "blow_off": ["blow_off"],
    "golpes_bobina": ["golpes_bobina_hora"],
    "golpes_turno": ["golpes_turno_hora"],
}
