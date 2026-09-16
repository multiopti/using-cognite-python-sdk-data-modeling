"""
Static configuration for the shift Excel report Function.

Keeps "Short Can - D&I y STD.xlsx" (customer-facing daily report, stored in
CDF Files) up to date each shift: fills in that shift's D&I/Standum
production/short-can/trimmer-jam totals for the machines CDF tracks, and
extends the file's blank-row scaffold far enough into the future so the
next run always has somewhere to write.
"""
from datetime import date, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=-4))
DATA_SET_ID = 5144187181631371
FILE_EXTERNAL_ID = "short_can_report"

# D&I-15 was added to the report going forward only (explicit instruction,
# not retroactive) starting this date -- never touch (FECHA, TURNO) groups
# before it. See handler._ensure_di15_rows.
DI15_INTRODUCED_DATE = date(2026, 9, 15)

# How many full days of blank scaffold rows to keep ahead of the shift just
# processed, so a missed run or two doesn't run the file out of rows to
# eventually fill.
SCAFFOLD_BUFFER_DAYS = 2

# Excel "MAQUINA" label -> CDF MACHINE_CONFIGS "code" (see
# functions/hourly_production_report/config.py). Machines with no CDF
# mapping (RAGS-19/20 aren't part of MACHINE_CONFIGS at all; D&I-16 is a
# machine code CDF doesn't read) map to None and their cells always stay
# blank, per explicit instruction.
MACHINE_MAP = {
    "STD-31": "standum31", "STD-32": "standum32", "STD-33": "standum33",
    "STD-34": "standum34", "STD-35": "standum35", "STD-36": "standum36",
    "STD-37": "standum37", "STD-38": "standum38",
    "D&I-11": "di11", "D&I-12": "di12", "D&I-14": "di14", "D&I-15": "di15",
    "D&I-17": "di17", "D&I-18": "di18",
    "D&I-16": None, "RAGS-19": None, "RAGS-20": None,
}

# Row order used both to read existing rows and to generate new scaffold
# rows in the right sequence (D&I-15 sits right after D&I-14, matching the
# sheet's numeric machine-code ordering).
STANDUN_MACHINES = ["STD-31", "STD-32", "STD-33", "STD-34", "STD-35", "STD-36", "STD-37", "STD-38"]
DI_MACHINES = ["D&I-11", "D&I-12", "D&I-14", "D&I-15", "D&I-16", "D&I-17", "D&I-18", "RAGS-19", "RAGS-20"]

TURNO_TO_SHIFT_CODE = {"1ER": "day", "1ERO": "day", "2DO": "night"}
SHIFT_CODE_TO_TURNO = {"day": "1ER", "night": "2DO"}

_PRODUCTION_KEYS = ["hourly_production"]
_SHORT_CAN_KEYS = ["short_cans_per_hour"]
_TRIMMER_JAM_KEYS = ["trimmer_jams_per_hour"]
