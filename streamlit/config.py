from datetime import date, datetime, timedelta, timezone

# Local operational timezone: GMT-4 fixed offset -- Venezuela does not
# observe daylight saving, matching functions/hourly_production_report's
# LOCAL_TZ constant.
LOCAL_TZ = timezone(timedelta(hours=-4))


def current_shift_defaults() -> tuple[date, str]:
    """
    (fecha, turno_label) for whichever shift is actually running right now,
    for the date/turno filters to default to on first load instead of always
    landing on today + day shift regardless of the real time.

    Day shift is 06:00-18:00 local, night shift is 18:00-06:00 -- and since
    night crosses midnight, its "shift date" is the date it STARTED, not
    today's calendar date. So between midnight and 06:00 local, this
    correctly returns YESTERDAY's date with the night shift, matching the
    external_id convention (report_{code}_{fecha}_{shift}) used everywhere
    else in this project, where a night-shift report already written at
    01:00 is filed under the previous day.
    """
    now_local = datetime.now(LOCAL_TZ)
    if 6 <= now_local.hour < 18:
        return now_local.date(), "6AM-6PM"
    shift_date = now_local.date() if now_local.hour >= 18 else now_local.date() - timedelta(days=1)
    return shift_date, "6PM-6AM"


MACHINE_GROUPS = {
    "MINSTER": ["MINSTER_L1", "MINSTER_L3"],
    "DI": ["DI11", "DI12", "DI14", "DI15", "DI17", "DI18"],
    "STANDUM": [
        "STANDUM31", "STANDUM32", "STANDUM33", "STANDUM34", 
        "STANDUM35", "STANDUM36", "STANDUM37", "STANDUM38"
    ],
    "PRINTER": ["P11", "P31", "P32"],
    "ISPRAY": [
        "ISPRAY11", "ISPRAY12", "ISPRAY13", "ISPRAY14", "ISPRAY15",
        "ISPRAY31", "ISPRAY32", "ISPRAY33", "ISPRAY34", "ISPRAY35", 
        "ISPRAY36", "ISPRAY37", "ISPRAY38"
    ]
}

SHIFT_MAP = {
    '6AM-6PM': 'day',
    '6PM-6AM': 'night'
}

DAY_HOURS = [
    "6AM-7AM", "7AM-8AM", "8AM-9AM", "9AM-10AM", "10AM-11AM", "11AM-12PM",
    "12PM-1PM", "1PM-2PM", "2PM-3PM", "3PM-4PM", "4PM-5PM", "5PM-6PM"
]

NIGHT_HOURS = [
    "6PM-7PM", "7PM-8PM", "8PM-9PM", "9PM-10PM", "10PM-11PM", "11PM-12AM",
    "12AM-1AM", "1AM-2AM", "2AM-3AM", "3AM-4AM", "4AM-5AM", "5AM-6AM"
]

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
    "Sin Personal / Ausentismo"
]

LOGO_URL = "https://static.wikia.nocookie.net/logopedia/images/d/d4/EmpresasPolar2010.png/revision/latest?cb=20200403161102&path-prefix=es"

CUSTOM_CSS = """
    <style>
    .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: 1rem !important;
    }
    .custom-title {
        margin-top: 15px !important;
        margin-bottom: 15px !important;
        font-weight: 700;
        color: #1e293b;
        font-size: 2.2rem;
    }
    div.stButton > button {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 0.4rem 1rem !important;
        transition: background-color 0.2s ease, transform 0.1s ease !important;
    }
    div.stButton > button:hover {
        background-color: #0369a1 !important;
        color: #ffffff !important;
    }
    div.stButton > button:active {
        background-color: #075985 !important;
        transform: scale(0.98);
    }
    </style>
"""

def get_display_columns(m_type: str) -> list:
    if m_type == "PRINTER":
        return ['Hora', 'Producción x hora', 'Retrac-x-hora', 'Blow of', 'Tiempo de parada', '% Eficiencia', 'Observaciones']
    elif m_type == "MINSTER":
        return ['Hora', 'Golpes Bobina', 'Golpes Turno', 'Tiempo Parada (min)', '% Eficiencia', 'Observaciones']
    elif m_type == "ISPRAY":
        return ['Hora', 'Producción x hora', 'Tiempo Parada (min)', '% Eficiencia', 'Observaciones']
    else:
        return [
            'Hora', 'PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER',
            'Merma (kg)',
            '% Merma', '% Eficiencia', 'Observaciones'
        ]