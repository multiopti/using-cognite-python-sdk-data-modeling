"""
Static configuration for the timeseries anomaly detector function.

MACHINE_CONFIGS is duplicated from functions/hourly_production_report/config.py
rather than imported -- each Cognite Function is deployed from its own
self-contained folder/zip, so cross-folder imports at deploy time don't work.
If a machine is added/removed/renamed, update both copies.
"""
from datetime import timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=-4))
DATA_SET_ID = 5144187181631371

# A step decrease landing below this value counts as a genuine counter reset
# (matches _RESET_TO_ZERO_EPS in hourly_production_report/handler.py). Any
# other downward step is noise/an anomaly worth flagging on its own.
RESET_TO_ZERO_EPS = 1.0

# "Running slower than usual" (production-type metrics): flag when this
# hour's value is below this fraction of the machine's normal per-shift
# running speed.
SLOW_RUNNING_RATIO = 0.5

# "More scrap/waste than usual" (scrap-type metrics): flag when this hour's
# value is at or above this multiple of the machine's normal per-shift rate.
EXCESS_SCRAP_RATIO = 2.0

# How many days back to look for the weekly-max / slow-running baselines.
BASELINE_WINDOW_DAYS = 7

MACHINE_CONFIGS = [
    # --- PRINTERS ---
    {
        "code": "p11",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L1_PRINTER",
        "ts_prod": "PRINTER_L1_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L1_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L1_LAT_SOP_ACT_DISP",
    },
    {
        "code": "p31",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L3_PRINTER_PRINTER31",
        "ts_prod": "PRINTER_L31_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L31_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L31_LAT_SOP_ACT_DISP",
    },
    {
        "code": "p32",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L3_PRINTER_PRINTER32",
        "ts_prod": "PRINTER_L32_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L32_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L32_LAT_SOP_ACT_DISP",
    },
    # --- D&I MACHINERY ---
    {"code": "di11", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI11",
     "ts_prod": "DI11_PROD_ACT_DISP", "ts_short_cans": "DI11_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI11_TRANC_TRIM_ACT_DISP"},
    {"code": "di12", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI12",
     "ts_prod": "DI12_PROD_ACT_DISP", "ts_short_cans": "DI12_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI12_TRANC_TRIM_ACT_DISP"},
    {"code": "di14", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI14",
     "ts_prod": "DI14_PROD_ACT_DISP", "ts_short_cans": "DI14_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI14_TRANC_TRIM_ACT_DISP"},
    {"code": "di15", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI15",
     "ts_prod": "DI15_PROD_ACT_DISP", "ts_short_cans": "DI15_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI15_TRANC_TRIM_ACT_DISP"},
    {"code": "di17", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI17",
     "ts_prod": "DI17_PROD_ACT_DISP", "ts_short_cans": "DI17_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI17_TRANC_TRIM_ACT_DISP"},
    {"code": "di18", "machine_type": "di", "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI18",
     "ts_prod": "DI18_PROD_ACT_DISP", "ts_short_cans": "DI18_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "DI18_TRANC_TRIM_ACT_DISP"},
    # --- STANDUM MACHINERY ---
    {"code": "standum31", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM31",
     "ts_prod": "STANDUM31_PROD_ACT_DISP", "ts_short_cans": "STANDUM31_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM31_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum32", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM32",
     "ts_prod": "STANDUM32_PROD_ACT_DISP", "ts_short_cans": "STANDUM32_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM32_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum33", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM33",
     "ts_prod": "STANDUM33_PROD_ACT_DISP", "ts_short_cans": "STANDUM33_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM33_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum34", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM34",
     "ts_prod": "STANDUM34_PROD_ACT_DISP", "ts_short_cans": "STANDUM34_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM34_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum35", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM35",
     "ts_prod": "STANDUM35_PROD_ACT_DISP", "ts_short_cans": "STANDUM35_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM35_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum36", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM36",
     "ts_prod": "STANDUM36_PROD_ACT_DISP", "ts_short_cans": "STANDUM36_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM36_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum37", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM37",
     "ts_prod": "STANDUM37_PROD_ACT_DISP", "ts_short_cans": "STANDUM37_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM37_TRANC_TRIM_ACUM_DISP"},
    {"code": "standum38", "machine_type": "standum", "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM38",
     "ts_prod": "STANDUM38_PROD_ACT_DISP", "ts_short_cans": "STANDUM38_PROD_LATAS_CORTAS_ACT_DISP", "ts_trimmer_jams": "STANDUM38_TRANC_TRIM_ACUM_DISP"},
    # --- MINSTER PRESSES ---
    {"code": "minster_l1", "machine_type": "minster", "asset_ext_id": "SuperenvasesMQTT_L1_MINSTER",
     "ts_golpes_bob": "MINSTER_L1_GOLPES_BOB_ACT_DISP", "ts_golpes_turno": "MINSTER_L1_GOLPES_TURNO_ACT_DISP"},
    {"code": "minster_l3", "machine_type": "minster", "asset_ext_id": "SuperenvasesMQTT_L3_MINSTER",
     "ts_golpes_bob": "MINSTER_L3_GOLPES_BOB_ACT_DISP", "ts_golpes_turno": "MINSTER_L3_GOLPES_TURNO_ACT_DISP"},
    # --- ISPRAY LINE 1 (11 - 15) ---
    {"code": "ispray11", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY11", "ts_prod": "IPSPRAY_L1_11_PROD_ACT_DISP"},
    {"code": "ispray12", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY12", "ts_prod": "IPSPRAY_L1_12_PROD_ACT_DISP"},
    {"code": "ispray13", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY13", "ts_prod": "IPSPRAY_L1_13_PROD_ACT_DISP"},
    {"code": "ispray14", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY14", "ts_prod": "IPSPRAY_L1_14_PROD_ACT_DISP"},
    {"code": "ispray15", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY15", "ts_prod": "IPSPRAY_L1_15_PROD_ACT_DISP"},
    # --- ISPRAY LINE 3 (31 - 38) ---
    {"code": "ispray31", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY31", "ts_prod": "IPSPRAY_L3_31_PROD_ACT_DISP"},
    {"code": "ispray32", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY32", "ts_prod": "IPSPRAY_L3_32_PROD_ACT_DISP"},
    {"code": "ispray33", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY33", "ts_prod": "IPSPRAY_L3_33_PROD_ACT_DISP"},
    {"code": "ispray34", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY34", "ts_prod": "IPSPRAY_L3_34_PROD_ACT_DISP"},
    {"code": "ispray35", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY35", "ts_prod": "IPSPRAY_L3_35_PROD_ACT_DISP"},
    {"code": "ispray36", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY36", "ts_prod": "IPSPRAY_L3_36_PROD_ACT_DISP"},
    {"code": "ispray37", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY37", "ts_prod": "IPSPRAY_L3_37_PROD_ACT_DISP"},
    {"code": "ispray38", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY38", "ts_prod": "IPSPRAY_L3_38_PROD_ACT_DISP"},
]

# Per machine_type: which raw timeseries keys to watch for reset/noise
# (patterns 1 & 2), and which field in the existing Production Report
# events holds that timeseries' already-computed hourly value (patterns
# 3 & 4 read this instead of re-deriving 7 days of raw deltas).
#
# "direction" controls which way is bad for the slow/excess baseline check:
#   PRODUCTION -- less than normal is the concern (SLOW_RUNNING).
#   SCRAP      -- more than normal is the concern (EXCESS_SCRAP). Matches
#                 short-cans/trimmer-jams already costing downtime minutes
#                 in hourly_production_report's own formula, and Printer's
#                 retract/blow-off (latas sopladas -- blown-off/rejected
#                 cans) representing waste, not output.
#
# Each entry: (ts_config_key, production_report_metadata_field, display_label, direction)
PRODUCTION = "PRODUCTION"
SCRAP = "SCRAP"

WATCHED_TIMESERIES = {
    "printer": [
        ("ts_prod", "hourly_production", "Producción", PRODUCTION),
        ("ts_retract", "hourly_retrac", "Retrac", SCRAP),
        ("ts_blow_off", "blow_off", "Blow off", SCRAP),
    ],
    "di": [
        ("ts_prod", "hourly_production", "Producción", PRODUCTION),
        ("ts_short_cans", "short_cans_per_hour", "Latas cortas", SCRAP),
        ("ts_trimmer_jams", "trimmer_jams_per_hour", "Trancamiento trimmer", SCRAP),
    ],
    "standum": [
        ("ts_prod", "hourly_production", "Producción", PRODUCTION),
        ("ts_short_cans", "short_cans_per_hour", "Latas cortas", SCRAP),
        ("ts_trimmer_jams", "trimmer_jams_per_hour", "Trancamiento trimmer", SCRAP),
    ],
    "minster": [
        ("ts_golpes_bob", "golpes_bobina_hora", "Golpes bobina", PRODUCTION),
        ("ts_golpes_turno", "golpes_turno_hora", "Golpes turno", PRODUCTION),
    ],
    "ispray": [
        ("ts_prod", "hourly_production", "Producción", PRODUCTION),
    ],
}

# The field used to decide whether a given historical hour counts as an
# "active" training sample for that machine (drives the baseline for every
# metric on that machine, not just this one) -- its own primary production
# count, matching what each machine's own efficiency formula already
# treats as "did it run this hour".
PRIMARY_FIELD = {
    "printer": "hourly_production",
    "di": "hourly_production",
    "standum": "hourly_production",
    "minster": "golpes_bobina_hora",
    "ispray": "hourly_production",
}

# Production Report subtype + machine-code metadata field per machine_type,
# needed to query the existing events for the weekly-max/slow-running baseline.
PRODUCTION_REPORT_SUBTYPE = {
    "printer": "Hourly Entry",
    "di": "Hourly Entry DI",
    "standum": "Hourly Entry Standum",
    "minster": "Hourly Entry MINSTER",
    "ispray": "Hourly Entry ISPRAY",
}
MACHINE_CODE_METADATA_FIELD = {
    "printer": "printer_code",
    "di": "machine_code",
    "standum": "machine_code",
    "minster": "machine_code",
    "ispray": "machine_code",
}
