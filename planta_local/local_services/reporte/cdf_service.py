"""Local replacement of streamlit/cdf_service.py (Reporte de Producción) for the plant server.

The hourly report rows are rebuilt from the plant's Node-RED weekly matrices with the same formulas as the CDF
Production Report events (planta_local/nodered_data.py). Only the last 7 days exist there. Observations are
read-only on the plant server (no CDF, and every operator shares the same access).
run_app.py puts this folder ahead of the app's own folder on sys.path when PLANT_DATA_SOURCE=nodered.
"""
import pandas as pd

import nodered_data as nd
from config import SHIFT_MAP                          # Reporte de Producción's own config

client = None   # main.py imports it for the CDF permission check; PLANT_READ_ONLY makes main.py skip that check


async def load_shift_report_from_cdf(machine_code: str, m_type: str, fecha_str: str, turno_label: str) -> pd.DataFrame:
    """Same columns as the CDF version: Slot + the machine type's report columns + Observaciones.
    Hours that have not finished yet are left out (main.py shows them empty, as with CDF)."""
    code = machine_code.lower()
    if code not in nd.MACHINES:
        raise RuntimeError(f"Máquina {machine_code} no configurada")
    shift_code = SHIFT_MAP.get(turno_label, "day")
    hours = nd.shift_hours(fecha_str, shift_code)
    oldest = nd.oldest_date()
    if hours[0].date() < oldest:
        raise RuntimeError(f"el servidor de planta solo tiene datos de la última semana: "
                           f"elija una fecha desde el {oldest:%d/%m/%Y}")
    rows = []
    for r in nd.shift_report(code, hours[0].date(), shift_code):
        if r["status"] == "pending":
            continue
        rows.append({"Slot": r["slot"], **r["row"], "Observaciones": r.get("obs", "Operación estándar")})
    return pd.DataFrame(rows) if rows else pd.DataFrame()


async def save_observations_to_cdf(*args, **kwargs) -> int:
    raise RuntimeError("el servidor de planta muestra el reporte en solo lectura: las observaciones no se guardan aquí")


async def fetch_heartbeat_status() -> str:
    """Status line at the bottom of the report: last successful read from Node-RED (red when old or failing)."""
    ok, text = nd.status()
    return text if ok else f":red[⚠️ {text}]"
