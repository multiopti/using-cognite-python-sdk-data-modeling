"""Local replacement of streamlit/cdf_service.py (Reporte de Producción) for the plant server.

The hourly report rows are rebuilt from the plant's Node-RED weekly matrices with the same formulas as the CDF
Production Report events (planta_local/nodered_data.py). Only the last 7 days exist there.

Hourly incidents ("Observaciones") are stored in FT Optix, one weekly matrix per machine, as the index of the chosen
option in config.INCIDENTES_OPCIONES (that list must only grow at the end). They are saved through Node-RED
(POST /api/observacion). An hour without a stored incident shows the automatic text (e.g. "Parada por latas cortas").
Whether operators may edit is decided by planta_server.py (PLANT_READ_ONLY); there is no per-user login.
run_app.py puts this folder ahead of the app's own folder on sys.path when PLANT_DATA_SOURCE=nodered.
"""
from types import SimpleNamespace

import pandas as pd
from cognite.client.data_classes.capabilities import EventsAcl

import nodered_data as nd
from config import INCIDENTES_OPCIONES, SHIFT_MAP   # Reporte de Producción's own config


async def _inspect():
    """Answers main.py's permission check (client.iam.token.inspect) with "may edit": on the plant server editing is
    controlled by PLANT_READ_ONLY, which main.py checks first."""
    return SimpleNamespace(capabilities=[SimpleNamespace(
        capability=EventsAcl([EventsAcl.Action.Read, EventsAcl.Action.Write], EventsAcl.Scope.All()))])


client = SimpleNamespace(iam=SimpleNamespace(token=SimpleNamespace(inspect=_inspect)))


def _incident_text(code):
    return INCIDENTES_OPCIONES[code] if isinstance(code, int) and 0 <= code < len(INCIDENTES_OPCIONES) else None


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
        obs = _incident_text(r.get("incident")) or r.get("obs", "Operación estándar")
        rows.append({"Slot": r["slot"], **r["row"], "Observaciones": obs})
    return pd.DataFrame(rows) if rows else pd.DataFrame()


async def save_observations_to_cdf(machine_code: str, fecha_str: str, turno_label: str,
                                   edited_df: pd.DataFrame, filtered_df: pd.DataFrame) -> int:
    """Saves, for each hour whose Observaciones changed, the chosen incident in Optix (through Node-RED).
    Only options of INCIDENTES_OPCIONES can be stored; hours that have not finished yet cannot be saved.
    Returns how many hours were saved; raises RuntimeError listing the hours that could not be saved."""
    shift_code = SHIFT_MAP.get(turno_label, "day")
    hours = nd.shift_hours(fecha_str, shift_code)
    saved, problems = 0, []
    original = filtered_df.reset_index(drop=True)
    edited = edited_df.reset_index(drop=True)
    for i in range(min(len(original), len(edited))):
        before, after = str(original.loc[i, "Observaciones"]), str(edited.loc[i, "Observaciones"])
        if after == before:
            continue
        slot = int(original.loc[i, "Slot"])
        label = str(original.loc[i, "Hora"]) if "Hora" in original else f"hora {slot}"
        if after not in INCIDENTES_OPCIONES:
            problems.append(f"{label}: '{after}' no es una incidencia de la lista")
            continue
        try:
            nd.save_incident(machine_code, hours[0].date(), shift_code, slot, INCIDENTES_OPCIONES.index(after))
            saved += 1
        except RuntimeError as e:
            problems.append(f"{label}: {e}")
    if saved:
        nd.invalidate()                          # show the new incidents on the next rerun
    if problems:
        raise RuntimeError(f"{saved} hora(s) guardada(s); no se guardaron: " + "; ".join(problems))
    return saved


async def fetch_heartbeat_status() -> str:
    """Status line at the bottom of the report: last successful read from Node-RED (red when old or failing)."""
    ok, text = nd.status()
    return text if ok else f":red[⚠️ {text}]"
