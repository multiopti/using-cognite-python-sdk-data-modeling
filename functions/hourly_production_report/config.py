"""
Static configuration for the hourly production report function.

Ported from notebooks/Notebooks_dataset_220726_113831_CreateHourlyReport.ipynb
-- no values changed, just moved out of the notebook so handler.py stays
readable. If a machine is added/removed/renamed, edit MACHINE_CONFIGS here.
"""
from datetime import timedelta, timezone

# Local operational timezone: GMT-4 (fixed offset -- Venezuela does not
# observe daylight saving, so this doesn't need to vary by date).
LOCAL_TZ = timezone(timedelta(hours=-4))

# D&I and Standum process constants
CANS_PER_SHORT_CAN = 5             # Cans lost per short can defect
CANS_PER_TRIMMER_JAM = 9           # Cans lost per trimmer jam
DOWNTIME_PER_SHORT_CAN_MIN = 5.0   # Minutes stopped per short can
DOWNTIME_PER_TRIM_JAM_MIN = 3.0    # Minutes stopped per trimmer jam
CAN_WEIGHT_KG = 0.0093             # Weight per aluminum can (~9.3g)
DATA_SET_ID = 5144187181631371

# Unified Machine Configurations
MACHINE_CONFIGS = [
    # --- PRINTERS ---
    {
        "code": "p11",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L1_PRINTER",
        "nominal_capacity": 66000.0,
        "ts_prod": "PRINTER_L1_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L1_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L1_LAT_SOP_ACT_DISP",
    },
    {
        "code": "p31",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L3_PRINTER_PRINTER31",
        "nominal_capacity": 120000.0,
        "ts_prod": "PRINTER_L31_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L31_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L31_LAT_SOP_ACT_DISP",
    },
    {
        "code": "p32",
        "machine_type": "printer",
        "asset_ext_id": "SuperenvasesMQTT_L3_PRINTER_PRINTER32",
        "nominal_capacity": 120000.0,
        "ts_prod": "PRINTER_L32_PROD_ACT_DISP",
        "ts_retract": "PRINTER_L32_RETRACT_ACT_DISP",
        "ts_blow_off": "PRINTER_L32_LAT_SOP_ACT_DISP",
    },
    # --- D&I MACHINERY ---
    {
        "code": "di11",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI11",
        "ts_prod": "DI11_PROD_ACT_DISP",
        "ts_short_cans": "DI11_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI11_TRANC_TRIM_ACT_DISP",
    },
    {
        "code": "di12",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI12",
        "ts_prod": "DI12_PROD_ACT_DISP",
        "ts_short_cans": "DI12_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI12_TRANC_TRIM_ACT_DISP",
    },
    {
        "code": "di14",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI14",
        "ts_prod": "DI14_PROD_ACT_DISP",
        "ts_short_cans": "DI14_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI14_TRANC_TRIM_ACT_DISP",
    },
    {
        "code": "di15",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI15",
        "ts_prod": "DI15_PROD_ACT_DISP",
        "ts_short_cans": "DI15_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI15_TRANC_TRIM_ACT_DISP",
    },
    {
        "code": "di17",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI17",
        "ts_prod": "DI17_PROD_ACT_DISP",
        "ts_short_cans": "DI17_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI17_TRANC_TRIM_ACT_DISP",
    },
    {
        "code": "di18",
        "machine_type": "di",
        "asset_ext_id": "SuperenvasesMQTT_L1_DI_DI18",
        "ts_prod": "DI18_PROD_ACT_DISP",
        "ts_short_cans": "DI18_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "DI18_TRANC_TRIM_ACT_DISP",
    },
    # --- STANDUM MACHINERY ---
    {
        "code": "standum31",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM31",
        "ts_prod": "STANDUM31_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM31_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM31_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum32",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM32",
        "ts_prod": "STANDUM32_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM32_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM32_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum33",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM33",
        "ts_prod": "STANDUM33_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM33_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM33_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum34",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM34",
        "ts_prod": "STANDUM34_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM34_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM34_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum35",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM35",
        "ts_prod": "STANDUM35_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM35_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM35_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum36",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM36",
        "ts_prod": "STANDUM36_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM36_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM36_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum37",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM37",
        "ts_prod": "STANDUM37_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM37_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM37_TRANC_TRIM_ACUM_DISP",
    },
    {
        "code": "standum38",
        "machine_type": "standum",
        "asset_ext_id": "SuperenvasesMQTT_L3_STANDUM_STANDUM38",
        "ts_prod": "STANDUM38_PROD_ACT_DISP",
        "ts_short_cans": "STANDUM38_PROD_LATAS_CORTAS_ACT_DISP",
        "ts_trimmer_jams": "STANDUM38_TRANC_TRIM_ACUM_DISP",
    },
    # --- MINSTER PRESSES ---
    {
        "code": "minster_l1",
        "machine_type": "minster",
        "asset_ext_id": "SuperenvasesMQTT_L1_MINSTER",
        "nominal_capacity": 7000.0,  # per hour; shift target = 7000 * 12 = 84000
        "ts_golpes_bob": "MINSTER_L1_GOLPES_BOB_ACT_DISP",
        "ts_golpes_turno": "MINSTER_L1_GOLPES_TURNO_ACT_DISP",
    },
    {
        "code": "minster_l3",
        "machine_type": "minster",
        "asset_ext_id": "SuperenvasesMQTT_L3_MINSTER",
        "nominal_capacity": 7000.0,  # per hour; shift target = 7000 * 12 = 84000
        "ts_golpes_bob": "MINSTER_L3_GOLPES_BOB_ACT_DISP",
        "ts_golpes_turno": "MINSTER_L3_GOLPES_TURNO_ACT_DISP",
    },
    # --- ISPRAY LINE 1 (11 - 15) ---
    {"code": "ispray11", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY11", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L1_11_PROD_ACT_DISP"},
    {"code": "ispray12", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY12", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L1_12_PROD_ACT_DISP"},
    {"code": "ispray13", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY13", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L1_13_PROD_ACT_DISP"},
    {"code": "ispray14", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY14", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L1_14_PROD_ACT_DISP"},
    {"code": "ispray15", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L1_ISPRAY_ISPRAY15", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L1_15_PROD_ACT_DISP"},
    # --- ISPRAY LINE 3 (31 - 38) ---
    {"code": "ispray31", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY31", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_31_PROD_ACT_DISP"},
    {"code": "ispray32", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY32", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_32_PROD_ACT_DISP"},
    {"code": "ispray33", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY33", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_33_PROD_ACT_DISP"},
    {"code": "ispray34", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY34", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_34_PROD_ACT_DISP"},
    {"code": "ispray35", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY35", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_35_PROD_ACT_DISP"},
    {"code": "ispray36", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY36", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_36_PROD_ACT_DISP"},
    {"code": "ispray37", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY37", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_37_PROD_ACT_DISP"},
    {"code": "ispray38", "machine_type": "ispray", "asset_ext_id": "SuperenvasesMQTT_L3_ISPRAY_ISPRAY38", "nominal_capacity": 16000.0, "ts_prod": "IPSPRAY_L3_38_PROD_ACT_DISP"},
]

HOUR_INTERVAL_MAP = {
    6: "6 a 7",    7: "7 a 8",    8: "8 a 9",    9: "9 a 10",
    10: "10 a 11", 11: "11 a 12", 12: "12 a 1",  13: "1 a 2",
    14: "2 a 3",   15: "3 a 4",   16: "4 a 5",   17: "5 a 6",
    18: "6 a 7",   19: "7 a 8",   20: "8 a 9",   21: "9 a 10",
    22: "10 a 11", 23: "11 a 12",  0: "12 a 1",   1: "1 a 2",
    2: "2 a 3",    3: "3 a 4",    4: "4 a 5",    5: "5 a 6",
}
