from datetime import date, timedelta

# Same day/night boundary convention as streamlit/config.py -- reused here so
# a date+shift picked in this app maps to the exact same external_id prefix
# (report_{code}_{fecha}_{shift}) the per-machine dashboard already uses.
SHIFT_MAP = {
    "6AM-6PM": "day",
    "6PM-6AM": "night",
}

LOGO_URL = "https://static.wikia.nocookie.net/logopedia/images/d/d4/EmpresasPolar2010.png/revision/latest?cb=20200403161102&path-prefix=es"

DATA_SET_ID = 5144187181631371

# Machine roster per line, grouped by type in real production-flow order
# (Minster stamps the can bodies -> D&I/Standum necks & trims -> Printer
# decorates -> ISpray coats) -- confirmed by the user for Line 1 and mirrored
# onto Line 3's equivalent stations.
LINES = {
    "Línea 1": {
        "minster": ["MINSTER_L1"],
        "di": ["DI11", "DI12", "DI14", "DI15", "DI17", "DI18"],
        "printer": ["P11"],
        "ispray": ["ISPRAY11", "ISPRAY12", "ISPRAY13", "ISPRAY14", "ISPRAY15"],
    },
    "Línea 3": {
        "minster": ["MINSTER_L3"],
        "standum": [
            "STANDUM31", "STANDUM32", "STANDUM33", "STANDUM34",
            "STANDUM35", "STANDUM36", "STANDUM37", "STANDUM38",
        ],
        "printer": ["P31", "P32"],
        "ispray": [
            "ISPRAY31", "ISPRAY32", "ISPRAY33", "ISPRAY34",
            "ISPRAY35", "ISPRAY36", "ISPRAY37", "ISPRAY38",
        ],
    },
}

# Display order of machine-type groups within each line (the flow order
# above) -- Línea 1 has no "standum" key, Línea 3 has no "di" key, so this is
# looked up per-line rather than assumed to be identical for both.
FLOW_ORDER = {
    "Línea 1": ["minster", "di", "printer", "ispray"],
    "Línea 3": ["minster", "standum", "printer", "ispray"],
}

TYPE_LABELS = {
    "minster": "Minster",
    "di": "D&I",
    "standum": "Standum",
    "printer": "Printer",
    "ispray": "ISpray",
}

# Matches the per-machine-type chart colors already established in
# streamlit/charts.py, so a color means the same thing in both apps.
TYPE_COLORS = {
    "minster": "#0284c7",
    "di": "#002B49",
    "standum": "#475569",
    "printer": "#0078D4",
    "ispray": "#10b981",
}

# Metadata key aliases per logical field -- handler.py uses different key
# names across the 5 event subtypes (e.g. Printer writes "efficiency" while
# everything else writes "pct_eficiencia", MINSTER's production proxy is
# "golpes_bobina_hora" not "hourly_production"). Listing every alias here
# lets one lookup function work for every machine type without a branch per
# type, mirroring the alias-fallback pattern already in streamlit/cdf_service.py.
PRODUCTION_KEYS = ["hourly_production", "golpes_bobina_hora"]
EFFICIENCY_KEYS = ["pct_eficiencia", "efficiency"]
DOWNTIME_KEYS = ["downtime_minutes", "total_downtime_min"]
# Scrap/waste counters: unlike the fields above, a single event can carry
# MORE THAN ONE of these at once (Standum/D&I write both short_cans_per_hour
# and trimmer_jams_per_hour), so these are summed rather than looked up as
# alternatives -- see cdf_service.sum_meta_num.
SCRAP_KEYS = ["short_cans_per_hour", "trimmer_jams_per_hour", "hourly_retrac", "blow_off"]

EFFICIENCY_TARGET_PCT = 85.0

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
        font-size: 1.9rem;
    }
    .line-panel {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 22px;
    }
    .line-panel-title {
        font-weight: 700;
        color: #1e293b;
        font-size: 1.05rem;
    }
    .line-panel-sub {
        font-size: 12px;
        color: #6b7280;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #F9FAFB;
        border-radius: 14px;
        padding: 5px 10px;
        font-size: 11px;
        color: #374151;
        margin: 3px 4px 3px 0;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    </style>
"""

STATUS_COLORS = {
    "running": "#16a34a",
    "idle": "#d97706",
    "failure": "#dc2626",
    "no_data": "#9ca3af",
}

STATUS_LABELS = {
    "running": "Operando",
    "idle": "Detenida",
    "failure": "Falla",
    "no_data": "Sin datos",
}


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def thirty_days_ago_str() -> str:
    return (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
