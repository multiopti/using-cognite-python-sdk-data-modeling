import asyncio
from datetime import date, timedelta
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cognite.client import AsyncCogniteClient
from cognite.client.data_classes import EventUpdate, EventWrite

# ---------------------------------------------------------
# 1. Page & Layout Configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Reporte de Producci車n", layout="wide")

st.markdown("""
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
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Initialize Cached Async Cognite Client & Constants
# ---------------------------------------------------------
@st.cache_resource
def get_cognite_client():
    return AsyncCogniteClient()

client = get_cognite_client()

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
    "Operaci車n est芍ndar",
    "Falla Mec芍nica",
    "Falla El谷ctrica",
    "Falla Neum芍tica / Hidr芍ulica",
    "Falta de Materia Prima / Insumos",
    "Ajuste / Calibraci車n de M芍quina",
    "Trancamiento / Atasco en L赤nea",
    "Mantenimiento Programado",
    "Mantenimiento No Programado",
    "Problema de Calidad / Inspecci車n",
    "Cambio de Formato / Herramental",
    "Limpieza Operativa",
    "Sin Personal / Ausentismo"
]

LOGO_URL = "https://static.wikia.nocookie.net/logopedia/images/d/d4/EmpresasPolar2010.png/revision/latest?cb=20200403161102&path-prefix=es"

# ---------------------------------------------------------
# 3. Top Logo
# ---------------------------------------------------------
try:
    st.image(LOGO_URL, width=130)
except Exception:
    pass

# ---------------------------------------------------------
# 4. State Initialization & Filter Callback
# ---------------------------------------------------------
today = date.today()
thirty_days_ago = today - timedelta(days=30)

if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {
        "fecha": today.strftime("%Y-%m-%d"),
        "m_type": "STANDUM",
        "machine_label": "STANDUM32",
        "machine_code": "standum32",
        "turno": "5AM-5PM"
    }

def apply_filters_callback():
    m_type_sel = st.session_state.get("input_m_type", "STANDUM")
    avail = MACHINE_GROUPS.get(m_type_sel, [])
    m_label = st.session_state.get("input_machine_label", avail[0] if avail else "")
    
    st.session_state.applied_filters = {
        "fecha": st.session_state.input_fecha.strftime("%Y-%m-%d") if st.session_state.get("input_fecha") else today.strftime("%Y-%m-%d"),
        "m_type": m_type_sel,
        "machine_label": m_label,
        "machine_code": m_label.lower(),
        "turno": st.session_state.get("input_turno", "5AM-5PM")
    }

applied = st.session_state.applied_filters
active_fecha = applied["fecha"]
active_m_type = applied["m_type"]
active_machine_label = applied["machine_label"]
active_machine_code = applied["machine_code"]
active_turno = applied["turno"]

# ---------------------------------------------------------
# 5. Operational Filter Bar
# ---------------------------------------------------------
filter_col1, filter_col2, filter_col3, filter_col4, btn_col = st.columns([2, 2, 2, 2, 1.5])

with filter_col1:
    st.date_input(
        "Fecha",
        value=pd.to_datetime(active_fecha).date(),
        min_value=thirty_days_ago,
        max_value=today,
        key="input_fecha"
    )

with filter_col2:
    selected_m_type = st.selectbox(
        "Tipo de M芍quina",
        options=list(MACHINE_GROUPS.keys()),
        index=list(MACHINE_GROUPS.keys()).index(active_m_type) if active_m_type in MACHINE_GROUPS else 0,
        key="input_m_type"
    )

with filter_col3:
    available_machines = MACHINE_GROUPS.get(selected_m_type, list(MACHINE_GROUPS.values())[0])
    m_index = available_machines.index(active_machine_label) if active_machine_label in available_machines else 0
    st.selectbox(
        "M芍quina",
        options=available_machines,
        index=m_index,
        key="input_machine_label"
    )

with filter_col4:
    turno_opts = ["5AM-5PM", "5PM-5AM"]
    t_index = turno_opts.index(active_turno) if active_turno in turno_opts else 0
    st.selectbox("Turno", options=turno_opts, index=t_index, key="input_turno")

with btn_col:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.button("Actualizar ??", use_container_width=True, on_click=apply_filters_callback)

# ---------------------------------------------------------
# 6. Main Report Title
# ---------------------------------------------------------
st.markdown(
    f"<h1 class='custom-title'>Reporte de Producci車n: {active_m_type} ({active_machine_label})</h1>", 
    unsafe_allow_html=True
)

st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. Timeline Template & Metadata Helpers
# ---------------------------------------------------------
active_hours = DAY_HOURS if active_turno == "5AM-5PM" else NIGHT_HOURS

full_shift_df = pd.DataFrame({
    "Slot": list(range(1, 13)),
    "Hora": active_hours
})

if active_m_type == "PRINTER":
    TABLE_DISPLAY_COLUMNS = [
        'Hora', 'Producci車n x hora', 'Retrac-x-hora', 'Blow of', 
        'Tiempo de parada', '% Eficiencia', 'Observaciones'
    ]
elif active_m_type == "MINSTER":
    TABLE_DISPLAY_COLUMNS = [
        'Hora', 'Golpes Bobina', 'Golpes Turno', 
        'Tiempo Parada (min)', '% Eficiencia', 'Observaciones'
    ]
elif active_m_type == "ISPRAY":
    TABLE_DISPLAY_COLUMNS = [
        'Hora', 'Producci車n x hora', 'Tiempo Parada (min)', 
        '% Eficiencia', 'Observaciones'
    ]
else:
    TABLE_DISPLAY_COLUMNS = [
        'Hora', 'PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER',
        'LAT x LAT CORTAS', 'LAT x TRANC TRIM',
        'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
        'Tiempo parada (min)', 'Merma (kg)',
        '% Merma', '% Eficiencia', 'Observaciones'
    ]

def get_meta_num(meta: dict, keys: list, default: float = 0.0) -> float:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            try:
                val_str = str(meta_lower[k_lower]).replace('%', '').strip()
                return float(val_str)
            except (ValueError, TypeError):
                continue
    return default

def get_meta_str(meta: dict, keys: list, default: str = "") -> str:
    meta_lower = {str(k).lower(): v for k, v in meta.items()}
    for k in keys:
        k_lower = k.lower()
        if k_lower in meta_lower and meta_lower[k_lower] is not None:
            return str(meta_lower[k_lower])
    return default

# ---------------------------------------------------------
# 8. Async CDF Data Loaders & Savers
# ---------------------------------------------------------
async def load_shift_report_from_cdf(machine_code: str, m_type: str, fecha_str: str, turno_label: str) -> pd.DataFrame:
    fecha_clean = fecha_str.replace("-", "")
    shift_code = SHIFT_MAP.get(turno_label, 'day')

    m_code_clean = machine_code.lower()
    alt_codes = [m_code_clean]
    
    if "minster" in m_code_clean or "min" in m_code_clean:
        if "1" in m_code_clean:
            alt_codes.extend(["minster_l1", "min11", "minster11"])
        elif "3" in m_code_clean:
            alt_codes.extend(["minster_l3", "min31", "minster31"])
    elif m_code_clean.startswith("std") or m_code_clean.startswith("standum"):
        alt_codes.extend([
            m_code_clean.replace("std", "standum"),
            m_code_clean.replace("standum", "std")
        ])
    elif m_code_clean.startswith("is") or m_code_clean.startswith("ispray"):
        alt_codes.extend([
            m_code_clean.replace("ispray", "is"),
            m_code_clean.replace("is", "ispray")
        ])

    candidate_prefixes = []
    for code in set(alt_codes):
        candidate_prefixes.extend([
            f"report_{code}_{fecha_clean}_{shift_code}",
            f"report_{code.upper()}_{fecha_clean}_{shift_code}",
            f"{code}_{fecha_clean}_{shift_code}"
        ])

    events = []
    for prefix in candidate_prefixes:
        res = await client.events.list(type="Production Report", external_id_prefix=prefix, limit=100)
        if res:
            events = list(res)
            break
        res_no_type = await client.events.list(external_id_prefix=prefix, limit=100)
        if res_no_type:
            events = list(res_no_type)
            break

    rows = []
    for evt in events:
        meta = getattr(evt, 'metadata', None) or {}
        ext_id = getattr(evt, 'external_id', '') or ''
        
        try:
            slot_num = int(ext_id.split("_entry_")[-1])
        except Exception:
            slot_num = int(meta.get('slot_index', meta.get('slot', 1)))

        if m_type == "PRINTER":
            rows.append({
                'Slot': slot_num,
                'Producci車n x hora': get_meta_num(meta, ['hourly_production', 'production', 'prod_hora', 'delta_prod']),
                'Retrac-x-hora': get_meta_num(meta, ['hourly_retrac', 'retrac', 'delta_retrac']),
                'Blow of': get_meta_num(meta, ['blow_off', 'blow_of', 'delta_blowoff']),
                'Tiempo de parada': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', 'efficiency', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operaci車n est芍ndar')
            })
        elif m_type == "MINSTER":
            rows.append({
                'Slot': slot_num,
                'Golpes Bobina': get_meta_num(meta, ['golpes_bobina_hora', 'golpes_bobina', 'coil_strokes']),
                'Golpes Turno': get_meta_num(meta, ['golpes_turno_hora', 'golpes_turno', 'shift_strokes']),
                'Tiempo Parada (min)': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operaci車n est芍ndar')
            })
        elif m_type == "ISPRAY":
            rows.append({
                'Slot': slot_num,
                'Producci車n x hora': get_meta_num(meta, ['hourly_production', 'production', 'prod_hora', 'delta_prod']),
                'Tiempo Parada (min)': get_meta_num(meta, ['downtime_minutes', 'tiempo_de_parada', 'downtime']),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operaci車n est芍ndar')
            })
        else:
            rows.append({
                'Slot': slot_num,
                'PROD. LATAS': get_meta_num(meta, ['hourly_production', 'prod. latas', 'prod_latas', 'production', 'delta_prod']),
                'LAT CORTAS': get_meta_num(meta, ['short_cans_per_hour', 'lat cortas', 'latas_cortas', 'delta_latas_cortas']),
                'TRANC TRIMMER': get_meta_num(meta, ['trimmer_jams_per_hour', 'tranc trimmer', 'trancamiento_trimmer', 'delta_tranc_trim']),
                'LAT x LAT CORTAS': get_meta_num(meta, ['cans_by_short_can', 'lat x lat cortas']),
                'LAT x TRANC TRIM': get_meta_num(meta, ['cans_by_trimmer_jam', 'lat x tranc trim']),
                'Tiempo prom de parada x lat cort (min)': get_meta_num(meta, ['downtime_by_short_can_min', 'tiempo prom de parada x lat cort (min)', 'prom de parada x lat cort (min)']),
                'Tiempo prom de parada x tranc trim (min)': get_meta_num(meta, ['downtime_by_trimmer_jam_min', 'tiempo prom de parada x tranc trim (min)', 'prom de parada x tranc trim (min)']),
                'Tiempo parada (min)': get_meta_num(meta, ['total_downtime_min', 'tiempo parada (min)', 'downtime_min']),
                'Merma (kg)': get_meta_num(meta, ['merma_kg', 'merma']),
                '% Merma': get_meta_str(meta, ['pct_merma', '% merma'], '0.00%'),
                '% Eficiencia': get_meta_str(meta, ['pct_eficiencia', '% eficiencia', 'eficiencia'], '0.00%'),
                'Observaciones': get_meta_str(meta, ['observations', 'observaciones', 'obs'], 'Operaci車n est芍ndar')
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()

async def save_observations_to_cdf(
    machine_code: str, 
    fecha_str: str, 
    turno_label: str, 
    edited_df: pd.DataFrame, 
    filtered_df: pd.DataFrame
) -> int:
    fecha_clean = fecha_str.replace("-", "")
    shift_code = SHIFT_MAP.get(turno_label, 'day')
    m_code_clean = machine_code.lower()
    prefix = f"report_{m_code_clean}_{fecha_clean}_{shift_code}"

    existing_events = await client.events.list(
        type="Production Report", 
        external_id_prefix=prefix, 
        limit=100
    )
    if not existing_events:
        existing_events = await client.events.list(
            external_id_prefix=prefix, 
            limit=100
        )

    event_map = {}
    for evt in existing_events:
        ext_id = getattr(evt, 'external_id', '') or (evt.get('external_id', '') if isinstance(evt, dict) else '')
        meta = getattr(evt, 'metadata', {}) or (evt.get('metadata', {}) if isinstance(evt, dict) else {})
        try:
            slot_num = int(ext_id.split("_entry_")[-1])
        except Exception:
            slot_num = int(meta.get('slot_index', meta.get('slot', 1)))
        event_map[slot_num] = evt

    events_to_create = []
    updates_to_send = []

    for idx, row in edited_df.iterrows():
        slot_num = int(filtered_df.loc[idx, 'Slot'])
        nueva_obs = str(row['Observaciones'])
        ext_id = f"{prefix}_entry_{slot_num}"

        if slot_num in event_map:
            existing_evt = event_map[slot_num]
            current_meta = getattr(existing_evt, 'metadata', None)
            if current_meta is None and isinstance(existing_evt, dict):
                current_meta = existing_evt.get('metadata', {})
            current_meta = dict(current_meta or {})
            
            if current_meta.get('observations') != nueva_obs or current_meta.get('observaciones') != nueva_obs:
                current_meta['observations'] = nueva_obs
                current_meta['observaciones'] = nueva_obs
                
                evt_id = getattr(existing_evt, 'id', None)
                if evt_id:
                    evt_update = EventUpdate(id=evt_id)
                else:
                    evt_update = EventUpdate(external_id=ext_id)
                
                evt_update.metadata.set(current_meta)
                updates_to_send.append(evt_update)
        else:
            new_meta = {
                "slot": str(slot_num),
                "slot_index": str(slot_num),
                "observations": nueva_obs,
                "observaciones": nueva_obs
            }
            for col in filtered_df.columns:
                if col not in ['Slot', 'Hora', 'Observaciones']:
                    new_meta[col.lower().replace(' ', '_')] = str(filtered_df.loc[idx, col])

            # Uso correcto de EventWrite para creaci車n de nuevos eventos en CDF SDK v7+
            events_to_create.append(
                EventWrite(
                    external_id=ext_id,
                    type="Production Report",
                    description=f"Reporte {m_code_clean} - Slot {slot_num}",
                    metadata=new_meta
                )
            )

    if updates_to_send:
        await client.events.update(updates_to_send)
    if events_to_create:
        await client.events.create(events_to_create)

    return len(updates_to_send) + len(events_to_create)

async def fetch_heartbeat_status() -> str:
    try:
        res = await client.time_series.data.retrieve_latest(external_id="ActivoSimulacion.HEARTBEAT")
        if res is None:
            return "Sin datos"

        if isinstance(res, (list, tuple)) or type(res).__name__.endswith("List"):
            if not res:
                return "Sin datos"
            dp = res[0]
        else:
            dp = res

        if getattr(dp, "has_datapoint", True) is False:
            return "Sin datos"

        timestamp = getattr(dp, 'timestamp', None)
        value = getattr(dp, 'value', None)

        if timestamp is not None:
            if isinstance(timestamp, (int, float)):
                dt_gmt4 = pd.to_datetime(timestamp, unit='ms') - timedelta(hours=4)
            else:
                dt_gmt4 = pd.to_datetime(timestamp) - timedelta(hours=4)

            dt_str = dt_gmt4.strftime("%Y-%m-%d %H:%M:%S")
            return f"{dt_str} (GMT-4) | Valor: {value}"
        elif value is not None:
            return f"Valor: {value}"

    except Exception as e:
        return f"Error leyendo heartbeat ({e})"
    return "Sin datos"

# Execute Queries
existing_df = pd.DataFrame()
try:
    existing_df = await load_shift_report_from_cdf(
        machine_code=active_machine_code, 
        m_type=active_m_type,
        fecha_str=active_fecha, 
        turno_label=active_turno
    )
except Exception as e:
    st.error(f"Error consultando eventos de CDF para {active_machine_label}: {e}")

# ---------------------------------------------------------
# 9. Merge Timeline with Event Data
# ---------------------------------------------------------
if not existing_df.empty:
    if 'Hora' in existing_df.columns:
        existing_df = existing_df.drop(columns=['Hora'])
    filtered_df = pd.merge(full_shift_df, existing_df, on="Slot", how="left")
else:
    filtered_df = full_shift_df.copy()

if active_m_type == "PRINTER":
    num_cols = ['Producci車n x hora', 'Retrac-x-hora', 'Blow of', 'Tiempo de parada']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operaci車n est芍ndar'}
elif active_m_type == "MINSTER":
    num_cols = ['Golpes Bobina', 'Golpes Turno', 'Tiempo Parada (min)']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operaci車n est芍ndar'}
elif active_m_type == "ISPRAY":
    num_cols = ['Producci車n x hora', 'Tiempo Parada (min)']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operaci車n est芍ndar'}
else:
    num_cols = [
        'PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER',
        'LAT x LAT CORTAS', 'LAT x TRANC TRIM',
        'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
        'Tiempo parada (min)', 'Merma (kg)'
    ]
    str_cols = {'% Merma': '0.00%', '% Eficiencia': '0.00%', 'Observaciones': 'Operaci車n est芍ndar'}

for col in num_cols:
    if col not in filtered_df.columns:
        filtered_df[col] = 0.0

for col, default_val in str_cols.items():
    if col not in filtered_df.columns:
        filtered_df[col] = default_val

filtered_df[num_cols] = filtered_df[num_cols].fillna(0.0)
for col, default_val in str_cols.items():
    filtered_df[col] = filtered_df[col].fillna(default_val)

filtered_df = filtered_df.sort_values('Slot').reset_index(drop=True)
filtered_df['Hora'] = filtered_df['Hora'].astype(str)

def get_avg_efficiency(df: pd.DataFrame) -> float:
    eff_series = df['% Eficiencia'].astype(str).str.replace('%', '').str.strip()
    eff_numeric = pd.to_numeric(eff_series, errors='coerce').fillna(0.0)
    non_zero = eff_numeric[eff_numeric > 0]
    return float(non_zero.mean()) if not non_zero.empty else 0.0

# ---------------------------------------------------------
# 10. Render Charts
# ---------------------------------------------------------
chart_col1, chart_col2 = st.columns(2)

if active_m_type == "PRINTER":
    with chart_col1:
        fig_prod_line = px.line(
            filtered_df, 
            x='Hora', 
            y='Producci車n x hora', 
            markers=True,
            labels={'Producci車n x hora': 'Unidades', 'Hora': 'Hora'},
            title=f"Producci車n por Hora: {active_machine_label} ({active_turno})"
        )
        fig_prod_line.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        fig_prod_line.update_traces(line=dict(color='#0078D4', width=3), marker=dict(size=7, color='#E81123', symbol='circle'))
        st.plotly_chart(fig_prod_line, use_container_width=True)

    with chart_col2:
        fig_retrac_bar = px.bar(
            filtered_df, 
            x='Hora', 
            y='Retrac-x-hora',
            labels={'Retrac-x-hora': 'Eventos', 'Hora': 'Hora'},
            title=f"Retrac por Hora: {active_machine_label} ({active_turno})",
            color_discrete_sequence=['#2B579A']
        )
        fig_retrac_bar.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        st.plotly_chart(fig_retrac_bar, use_container_width=True)

elif active_m_type == "MINSTER":
    with chart_col1:
        fig_strokes_line = px.line(
            filtered_df, 
            x='Hora', 
            y='Golpes Bobina', 
            markers=True,
            labels={'Golpes Bobina': 'Golpes', 'Hora': 'Hora'},
            title=f"Golpes de Bobina por Hora: {active_machine_label} ({active_turno})"
        )
        fig_strokes_line.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        fig_strokes_line.update_traces(line=dict(color='#0284c7', width=3), marker=dict(size=7, color='#0f172a', symbol='circle'))
        st.plotly_chart(fig_strokes_line, use_container_width=True)

    with chart_col2:
        fig_stop_bar = px.bar(
            filtered_df, 
            x='Hora', 
            y='Tiempo Parada (min)',
            labels={'Tiempo Parada (min)': 'Minutos', 'Hora': 'Hora'},
            title=f"Tiempo de Parada por Hora: {active_machine_label} ({active_turno})",
            color_discrete_sequence=['#ef4444']
        )
        fig_stop_bar.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        st.plotly_chart(fig_stop_bar, use_container_width=True)

elif active_m_type == "ISPRAY":
    with chart_col1:
        fig_prod_ispray = px.line(
            filtered_df, 
            x='Hora', 
            y='Producci車n x hora', 
            markers=True,
            labels={'Producci車n x hora': 'Latas', 'Hora': 'Hora'},
            title=f"Latas Recubiertas (iSpray): {active_machine_label} ({active_turno})"
        )
        fig_prod_ispray.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        fig_prod_ispray.update_traces(line=dict(color='#10b981', width=3), marker=dict(size=7, color='#047857', symbol='circle'))
        st.plotly_chart(fig_prod_ispray, use_container_width=True)

    with chart_col2:
        fig_ispray_stop = px.bar(
            filtered_df, 
            x='Hora', 
            y='Tiempo Parada (min)',
            labels={'Tiempo Parada (min)': 'Minutos', 'Hora': 'Hora'},
            title=f"Tiempo Parada iSpray: {active_machine_label} ({active_turno})",
            color_discrete_sequence=['#f59e0b']
        )
        fig_ispray_stop.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        st.plotly_chart(fig_ispray_stop, use_container_width=True)

else:
    with chart_col1:
        fig_prod_line = px.line(
            filtered_df, 
            x='Hora', 
            y='PROD. LATAS', 
            markers=True,
            labels={'PROD. LATAS': 'Latas Producidas', 'Hora': 'Hora'},
            title=f"Producci車n por Hora: {active_machine_label} ({active_turno})"
        )
        fig_prod_line.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        fig_prod_line.update_traces(line=dict(color='#002B49', width=3), marker=dict(size=7, color='#E81123', symbol='circle'))
        st.plotly_chart(fig_prod_line, use_container_width=True)

    with chart_col2:
        fig_di_events = go.Figure()
        fig_di_events.add_trace(go.Bar(x=filtered_df["Hora"], y=filtered_df["LAT CORTAS"], name="Latas Cortas", marker_color="#D62728"))
        fig_di_events.add_trace(go.Bar(x=filtered_df["Hora"], y=filtered_df["TRANC TRIMMER"], name="Tranc. Trimmer", marker_color="#9467BD"))
        fig_di_events.update_layout(
            barmode="stack", plot_bgcolor='white', paper_bgcolor='white',
            xaxis=dict(type='category', showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
            height=250, title=f"Merma x hora: {active_machine_label} ({active_turno})",
            title_font=dict(size=14), margin=dict(t=35, b=25, l=40, r=40)
        )
        st.plotly_chart(fig_di_events, use_container_width=True)

# ---------------------------------------------------------
# 11. Gauges Section
# ---------------------------------------------------------
st.markdown("<hr style='margin-top: 5px; margin-bottom: 5px;' />", unsafe_allow_html=True)
gauge_col1, gauge_col2, gauge_col3, gauge_col4 = st.columns(4)

if active_m_type == "PRINTER":
    total_prod = int(filtered_df['Producci車n x hora'].sum())
    total_retrac = int(filtered_df['Retrac-x-hora'].sum())
    total_blow = int(filtered_df['Blow of'].sum())
    total_downtime = round(filtered_df['Tiempo de parada'].sum(), 1)

    with gauge_col1:
        fig_prod = go.Figure(go.Indicator(
            mode="gauge+number", value=total_prod,
            title={'text': "Producci車n Total (Turno)", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720000], 'tickvals': [0, 200000, 400000, 600000, 720000], 'ticktext': ['0', '200k', '400k', '600k', '720k'], 'tickfont': {'size': 10}},
                   'bar': {'color': "#0078D4"},
                   'steps': [{'range': [0, 396000], 'color': "#FFCCCC"}, {'range': [396000, 720000], 'color': "#E6E6E6"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 396000}}
        ))
        fig_prod.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_prod, use_container_width=True)

    with gauge_col2:
        fig_retrac = go.Figure(go.Indicator(
            mode="gauge+number", value=total_retrac,
            title={'text': "Retrac Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 1000], 'tickfont': {'size': 10}}, 'bar': {'color': "#2B579A"},
                   'steps': [{'range': [0, 800], 'color': "#E6E6E6"}, {'range': [800, 1000], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 800}}
        ))
        fig_retrac.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_retrac, use_container_width=True)

    with gauge_col3:
        fig_blow = go.Figure(go.Indicator(
            mode="gauge+number", value=total_blow,
            title={'text': "Blow off Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 1000], 'tickfont': {'size': 10}}, 'bar': {'color': "#2B579A"},
                   'steps': [{'range': [0, 800], 'color': "#E6E6E6"}, {'range': [800, 1000], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 800}}
        ))
        fig_blow.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_blow, use_container_width=True)

    with gauge_col4:
        fig_stop = go.Figure(go.Indicator(
            mode="gauge+number", value=total_downtime, number={'suffix': ' min'},
            title={'text': "Tiempo Parada Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720], 'tickfont': {'size': 10}}, 'bar': {'color': "#515151"},
                   'steps': [{'range': [0, 360], 'color': "#E6E6E6"}, {'range': [360, 720], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 360}}
        ))
        fig_stop.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_stop, use_container_width=True)

elif active_m_type == "MINSTER":
    total_golpes_bobina = int(filtered_df['Golpes Bobina'].sum())
    total_golpes_turno = int(filtered_df['Golpes Turno'].sum())
    avg_eff = get_avg_efficiency(filtered_df)
    total_downtime_min = round(filtered_df['Tiempo Parada (min)'].sum(), 1)

    with gauge_col1:
        fig_gb = go.Figure(go.Indicator(
            mode="gauge+number", value=total_golpes_bobina,
            title={'text': "Total Golpes Bobina", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 25000], 'tickfont': {'size': 10}},
                   'bar': {'color': "#0284c7"},
                   'steps': [{'range': [0, 15000], 'color': "#FFCCCC"}, {'range': [15000, 25000], 'color': "#E6E6E6"}]}
        ))
        fig_gb.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_gb, use_container_width=True)

    with gauge_col2:
        fig_gt = go.Figure(go.Indicator(
            mode="gauge+number", value=total_golpes_turno,
            title={'text': "Total Golpes Turno", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 25000], 'tickfont': {'size': 10}},
                   'bar': {'color': "#38bdf8"},
                   'steps': [{'range': [0, 15000], 'color': "#FFCCCC"}, {'range': [15000, 25000], 'color': "#E6E6E6"}]}
        ))
        fig_gt.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_gt, use_container_width=True)

    with gauge_col3:
        fig_eff = go.Figure(go.Indicator(
            mode="gauge+number", value=round(avg_eff, 1), number={'suffix': '%'},
            title={'text': "Eficiencia Promedio", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 100], 'tickfont': {'size': 10}},
                   'bar': {'color': "#10b981"},
                   'steps': [{'range': [0, 75], 'color': "#FFCCCC"}, {'range': [75, 100], 'color': "#E6E6E6"}]}
        ))
        fig_eff.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_eff, use_container_width=True)

    with gauge_col4:
        fig_stop = go.Figure(go.Indicator(
            mode="gauge+number", value=total_downtime_min, number={'suffix': ' min'},
            title={'text': "Tiempo Parada Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720], 'tickfont': {'size': 10}}, 'bar': {'color': "#ef4444"},
                   'steps': [{'range': [0, 360], 'color': "#E6E6E6"}, {'range': [360, 720], 'color': "#FFCCCC"}]}
        ))
        fig_stop.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_stop, use_container_width=True)

elif active_m_type == "ISPRAY":
    total_cans_ispray = int(filtered_df['Producci車n x hora'].sum())
    avg_eff_ispray = get_avg_efficiency(filtered_df)
    total_downtime_ispray = round(filtered_df['Tiempo Parada (min)'].sum(), 1)

    with gauge_col1:
        fig_ispray_prod = go.Figure(go.Indicator(
            mode="gauge+number", value=total_cans_ispray,
            title={'text': "Total Latas Recubiertas", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 20000], 'tickfont': {'size': 10}},
                   'bar': {'color': "#10b981"},
                   'steps': [{'range': [0, 10000], 'color': "#FFCCCC"}, {'range': [10000, 20000], 'color': "#E6E6E6"}]}
        ))
        fig_ispray_prod.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_ispray_prod, use_container_width=True)

    with gauge_col2:
        fig_ispray_eff = go.Figure(go.Indicator(
            mode="gauge+number", value=round(avg_eff_ispray, 1), number={'suffix': '%'},
            title={'text': "Eficiencia Promedio", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 100], 'tickfont': {'size': 10}},
                   'bar': {'color': "#059669"},
                   'steps': [{'range': [0, 75], 'color': "#FFCCCC"}, {'range': [75, 100], 'color': "#E6E6E6"}]}
        ))
        fig_ispray_eff.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_ispray_eff, use_container_width=True)

    with gauge_col3:
        fig_ispray_stop = go.Figure(go.Indicator(
            mode="gauge+number", value=total_downtime_ispray, number={'suffix': ' min'},
            title={'text': "Tiempo Parada Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720], 'tickfont': {'size': 10}}, 'bar': {'color': "#f59e0b"},
                   'steps': [{'range': [0, 360], 'color': "#E6E6E6"}, {'range': [360, 720], 'color': "#FFCCCC"}]}
        ))
        fig_ispray_stop.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_ispray_stop, use_container_width=True)

    with gauge_col4:
        active_hours_count = int((filtered_df['Producci車n x hora'] > 0).sum())
        fig_active_hrs = go.Figure(go.Indicator(
            mode="number", value=active_hours_count,
            title={'text': "Horas Activas (Turno)", 'font': {'size': 13}},
            number={'suffix': ' / 12 hrs'}
        ))
        fig_active_hrs.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_active_hrs, use_container_width=True)

else:
    total_prod_di = int(filtered_df['PROD. LATAS'].sum())
    total_short_can = int(filtered_df['LAT CORTAS'].sum())
    total_trimmer = int(filtered_df['TRANC TRIMMER'].sum())
    total_downtime_di = round(filtered_df['Tiempo parada (min)'].sum(), 1)

    with gauge_col1:
        fig_prod = go.Figure(go.Indicator(
            mode="gauge+number", value=total_prod_di,
            title={'text': "Producci車n Total (Latas)", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720000], 'tickvals': [0, 200000, 400000, 600000, 720000], 'ticktext': ['0', '200k', '400k', '600k', '720k'], 'tickfont': {'size': 10}},
                   'bar': {'color': "#002B49"},
                   'steps': [{'range': [0, 396000], 'color': "#FFCCCC"}, {'range': [396000, 720000], 'color': "#E6E6E6"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 396000}}
        ))
        fig_prod.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_prod, use_container_width=True)

    with gauge_col2:
        fig_short = go.Figure(go.Indicator(
            mode="gauge+number", value=total_short_can,
            title={'text': "Latas Cortas Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 500], 'tickfont': {'size': 10}}, 'bar': {'color': "#D62728"},
                   'steps': [{'range': [0, 300], 'color': "#E6E6E6"}, {'range': [300, 500], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 300}}
        ))
        fig_short.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_short, use_container_width=True)

    with gauge_col3:
        fig_trim = go.Figure(go.Indicator(
            mode="gauge+number", value=total_trimmer,
            title={'text': "Trancamientos Trimmer", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 100], 'tickfont': {'size': 10}}, 'bar': {'color': "#9467BD"},
                   'steps': [{'range': [0, 50], 'color': "#E6E6E6"}, {'range': [50, 100], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 50}}
        ))
        fig_trim.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_trim, use_container_width=True)

    with gauge_col4:
        fig_stop = go.Figure(go.Indicator(
            mode="gauge+number", value=total_downtime_di, number={'suffix': ' min'},
            title={'text': "Tiempo Parada Total", 'font': {'size': 13}},
            gauge={'axis': {'range': [0, 720], 'tickfont': {'size': 10}}, 'bar': {'color': "#515151"},
                   'steps': [{'range': [0, 360], 'color': "#E6E6E6"}, {'range': [360, 720], 'color': "#FFCCCC"}],
                   'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': 360}}
        ))
        fig_stop.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_stop, use_container_width=True)

# ---------------------------------------------------------
# 12. Format Display Table & Interactive Data Editor
# ---------------------------------------------------------
st.markdown("### Detalle Horario del Turno")

display_df = filtered_df[TABLE_DISPLAY_COLUMNS].copy()

if active_m_type == "PRINTER":
    for int_col in ['Producci車n x hora', 'Retrac-x-hora', 'Blow of']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo de parada'] = display_df['Tiempo de parada'].apply(lambda x: f"{float(x):.2f}")

elif active_m_type == "MINSTER":
    for int_col in ['Golpes Bobina', 'Golpes Turno']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo Parada (min)'] = display_df['Tiempo Parada (min)'].apply(lambda x: f"{float(x):.2f}")

elif active_m_type == "ISPRAY":
    display_df['Producci車n x hora'] = display_df['Producci車n x hora'].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo Parada (min)'] = display_df['Tiempo Parada (min)'].apply(lambda x: f"{float(x):.2f}")

else:
    for int_col in ['PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER', 'LAT x LAT CORTAS', 'LAT x TRANC TRIM']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    for float_col in [
        'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
        'Tiempo parada (min)', 'Merma (kg)'
    ]:
        display_df[float_col] = display_df[float_col].apply(lambda x: f"{float(x):.2f}")

display_df = display_df.astype(str)

obs_existentes = [obs for obs in display_df['Observaciones'].unique().tolist() if obs]
opciones_desplegable = list(dict.fromkeys(INCIDENTES_OPCIONES + obs_existentes))

read_only_cols = [c for c in display_df.columns if c != 'Observaciones']

edited_df = st.data_editor(
    display_df,
    column_config={
        "Observaciones": st.column_config.SelectboxColumn(
            "Observaciones / Incidencias",
            help="Seleccione la falla o evento principal ocurrido en el bloque horario",
            width="large",
            options=opciones_desplegable,
            required=True
        )
    },
    disabled=read_only_cols,
    use_container_width=True,
    hide_index=True,
    key="table_editor"
)

# ---------------------------------------------------------
# 12.1. Bot車n para Guardar Cambios en CDF
# ---------------------------------------------------------
st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
btn_save_col1, btn_save_col2 = st.columns([2.5, 5])

with btn_save_col1:
    if st.button("Guardar Cambios ??", use_container_width=True):
        try:
            with st.spinner("Guardando observaciones en Cognite Data Fusion..."):
                total_mod = await save_observations_to_cdf(
                    machine_code=active_machine_code,
                    fecha_str=active_fecha,
                    turno_label=active_turno,
                    edited_df=edited_df,
                    filtered_df=filtered_df
                )
            if total_mod > 0:
                st.success(f"?{total_mod} registro(s) actualizados correctamente en CDF! ??")
            else:
                st.info("No se detectaron cambios pendientes por guardar.")
        except Exception as e:
            st.error(f"Error al guardar los cambios en CDF: {e}")

# ---------------------------------------------------------
# 13. Edge Heartbeat Footer
# ---------------------------------------------------------
heartbeat_val = await fetch_heartbeat_status()
st.markdown(f"**Last Heartbeat:** {heartbeat_val}")