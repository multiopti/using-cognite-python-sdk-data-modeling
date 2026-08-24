"""
Static configuration for the anomaly monitor Streamlit app: severity/color
mapping for each pattern the timeseries_anomaly_detector function writes,
plus a couple of small display helpers.
"""

DATA_SET_ID = 5144187181631371

# One entry per pattern the function can write (see
# functions/timeseries_anomaly_detector/handler.py). Order here is also the
# default sort priority (most critical first) when grouping/summarizing.
PATTERN_INFO = {
    "EXCESS_SCRAP": {
        "label": "Exceso de merma",
        "severity": "critical",
        "color": "#dc2626",       # red
        "bg": "#FEF2F2",
        "icon": "🔴",
    },
    "SLOW_RUNNING": {
        "label": "Operando más lento",
        "severity": "warning",
        "color": "#ea580c",       # orange
        "bg": "#FFF7ED",
        "icon": "🟠",
    },
    "NONZERO_DECREASE": {
        "label": "Posible ruido de sensor",
        "severity": "warning",
        "color": "#ea580c",       # orange
        "bg": "#FFF7ED",
        "icon": "🟠",
    },
    "RESET_TO_ZERO": {
        "label": "Reinicio de contador",
        "severity": "info",
        "color": "#6b7280",       # gray
        "bg": "#F9FAFB",
        "icon": "⚪",
    },
    "NEW_WEEKLY_MAX": {
        "label": "Nuevo máximo semanal",
        "severity": "positive",
        "color": "#16a34a",       # green
        "bg": "#F0FDF4",
        "icon": "🟢",
    },
}

# Severity display order (for the filter and for sorting within a group).
SEVERITY_ORDER = ["critical", "warning", "info", "positive"]
SEVERITY_LABELS = {
    "critical": "Crítico",
    "warning": "Advertencia",
    "info": "Informativo",
    "positive": "Positivo",
}

MACHINE_TYPE_LABELS = {
    "printer": "PRINTER",
    "di": "D&I",
    "standum": "STANDUM",
    "minster": "MINSTER",
    "ispray": "ISPRAY",
}

LOGO_URL = "https://static.wikia.nocookie.net/logopedia/images/d/d4/EmpresasPolar2010.png/revision/latest?cb=20200403161102&path-prefix=es"

CUSTOM_CSS = """
    <style>
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 1rem !important;
    }
    .custom-title {
        margin-top: 10px !important;
        margin-bottom: 5px !important;
        font-weight: 700;
        color: #1e293b;
        font-size: 2rem;
    }
    .event-card {
        border-left: 5px solid #cccccc;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 10px;
        background-color: #ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }
    .event-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 4px;
    }
    .event-title {
        font-weight: 700;
        font-size: 15px;
    }
    .event-time {
        font-size: 12px;
        color: #6b7280;
    }
    .event-desc {
        font-size: 14px;
        color: #1f2937;
        margin: 2px 0 4px 0;
    }
    .event-meta {
        font-size: 12px;
        color: #6b7280;
    }
    </style>
"""
