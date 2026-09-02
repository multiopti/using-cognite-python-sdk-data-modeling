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

# NEW_WEEKLY_MAX fires on both production metrics (a new high is good) and
# scrap/waste metrics (a new high is bad) -- see WATCHED_TIMESERIES in
# functions/timeseries_anomaly_detector/config.py, whose "direction" this
# label set mirrors (kept separate on purpose: this app shares no code or
# deploy with that Function). resolve_pattern_info() below uses it to flip
# NEW_WEEKLY_MAX to red/critical for scrap metrics instead of green/positive.
SCRAP_LABELS = {"Retrac", "Blow off", "Latas cortas", "Trancamiento trimmer"}

NEW_WEEKLY_MAX_SCRAP_INFO = {
    "label": "Nuevo máximo semanal (merma)",
    "severity": "critical",
    "color": "#dc2626",       # red
    "bg": "#FEF2F2",
    "icon": "🔴",
}


def resolve_pattern_info(pattern: str, timeseries_label: str | None = None) -> dict:
    """Like PATTERN_INFO[pattern], except NEW_WEEKLY_MAX on a scrap/waste
    metric (e.g. Latas cortas, Trancamiento trimmer) resolves to red/critical
    instead of the pattern's default green/positive."""
    if pattern == "NEW_WEEKLY_MAX" and timeseries_label in SCRAP_LABELS:
        return NEW_WEEKLY_MAX_SCRAP_INFO
    return PATTERN_INFO.get(pattern, {"label": pattern, "severity": "info", "color": "#999999", "bg": "#f5f5f5", "icon": "⚪"})


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
