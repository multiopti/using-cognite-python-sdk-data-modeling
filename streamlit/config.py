from datetime import date, timedelta

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
    '5AM-5PM': 'day',
    '5PM-5AM': 'night'
}

DAY_HOURS = [
    "5AM-6AM", "6AM-7AM", "7AM-8AM", "8AM-9AM", "9AM-10AM", "10AM-11AM",
    "11AM-12PM", "12PM-1PM", "1PM-2PM", "2PM-3PM", "3PM-4PM", "4PM-5PM"
]

NIGHT_HOURS = [
    "5PM-6PM", "6PM-7PM", "7PM-8PM", "8PM-9PM", "9PM-10PM", "10PM-11PM",
    "11PM-12AM", "12AM-1AM", "1AM-2AM", "2AM-3AM", "3AM-4AM", "4AM-5AM"
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
            'LAT x LAT CORTAS', 'LAT x TRANC TRIM',
            'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
            'Tiempo parada (min)', 'Merma (kg)',
            '% Merma', '% Eficiencia', 'Observaciones'
        ]