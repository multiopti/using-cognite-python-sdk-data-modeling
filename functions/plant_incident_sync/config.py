"""Configuration for plant_incident_sync (plant hourly incidents -> CDF Production Report events).

Cognite Functions can't import code from other folders, so the two lists below are COPIES. Keep them in sync:
  - INCIDENTES_OPCIONES: streamlit/config.py. It is append-only (Optix stores the position in the list), so a new
    option there only needs appending here too, then redeploying this function. test_handler.py checks the copy.
  - OBS_KEY_TO_CODE: Optix matrix key (Model/OBSERVACIONES/<key>_OBS_DATA_WEEK) -> machine "code" in
    functions/hourly_production_report/config.py MACHINE_CONFIGS (the one planta_local/nodered_data.py derives).
"""
from datetime import timedelta, timezone

# Where the CDF hosted extractor job (topic SuperenvasesIncidents/#) stores each MQTT message
RAW_DB = "db_superenvases_raw"
RAW_TABLE = "raw_incident_snapshots"
SNAPSHOT_TAG = "INCIDENTS_SNAPSHOT"          # the record Optix's MQTTPublisherIncidents sends

# Only act on a snapshot this recent. Optix publishes every 5 minutes; with no recent snapshot (plant offline)
# nothing is done, and the next snapshot after the outage brings everything up to date.
MAX_AGE_MINUTES = 30

EVENT_TYPE = "Production Report"
LOCAL_TZ = timezone(timedelta(hours=-4))     # plant time (UTC-4, no DST), as in hourly_production_report

INCIDENTES_OPCIONES = [
    "Operación estándar",
    "Falla Mecánica",
    "Falla Eléctrica",
    "Falla Neumática / Hidráulica",
    "Falta de Materia Prima / Insumos",
    "Ajuste / Calibración de Máquina",
    "Trancamiento / Atasco en Línea",
    "Mantenimiento Programado",
    "Mantenimiento No Programado",
    "Problema de Calidad / Inspección",
    "Cambio de Formato / Herramental",
    "Limpieza Operativa",
    "Sin Personal / Ausentismo",
]

OBS_KEY_TO_CODE = {
    "PRINTER_L1": "p11", "PRINTER_L31": "p31", "PRINTER_L32": "p32",
    "DI11": "di11", "DI12": "di12", "DI14": "di14", "DI15": "di15", "DI17": "di17", "DI18": "di18",
    "STANDUM31": "standum31", "STANDUM32": "standum32", "STANDUM33": "standum33", "STANDUM34": "standum34",
    "STANDUM35": "standum35", "STANDUM36": "standum36", "STANDUM37": "standum37", "STANDUM38": "standum38",
    "MINSTER_L1": "minster_l1", "MINSTER_L3": "minster_l3",
    "IPSPRAY_L1_11": "ispray11", "IPSPRAY_L1_12": "ispray12", "IPSPRAY_L1_13": "ispray13",
    "IPSPRAY_L1_14": "ispray14", "IPSPRAY_L1_15": "ispray15",
    "IPSPRAY_L3_31": "ispray31", "IPSPRAY_L3_32": "ispray32", "IPSPRAY_L3_33": "ispray33",
    "IPSPRAY_L3_34": "ispray34", "IPSPRAY_L3_35": "ispray35", "IPSPRAY_L3_36": "ispray36",
    "IPSPRAY_L3_37": "ispray37", "IPSPRAY_L3_38": "ispray38",
}
