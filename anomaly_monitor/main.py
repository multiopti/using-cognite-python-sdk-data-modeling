import streamlit as st

# OBLIGATORIO: debe ser el primer comando de Streamlit que se ejecute
st.set_page_config(page_title="Monitor de Anomalías", layout="wide")

import base64
import html
import io

from config import (
    CUSTOM_CSS,
    LOGO_B64,
    MACHINE_TYPE_LABELS,
    PATTERN_INFO,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    resolve_pattern_info,
)
from cdf_service import load_anomaly_events

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

try:
    st.image(io.BytesIO(base64.b64decode(LOGO_B64)), width=130)
except Exception:
    pass

st.markdown("<h1 class='custom-title'>Monitor de Anomalías -- Contadores</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='color:#6b7280; margin-bottom: 10px;'>"
    "Detecciones automáticas sobre los contadores de planta: reinicios, ruido de sensor, "
    "récords semanales, operación más lenta de lo usual y exceso de merma."
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Filter bar
# ---------------------------------------------------------
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.2, 1.5, 1.5, 2.5])

with filter_col1:
    days_back = st.number_input("Días hacia atrás", min_value=1, max_value=30, value=7, step=1)

with filter_col2:
    machine_type_opts = ["Todos"] + list(MACHINE_TYPE_LABELS.values())
    selected_type_label = st.selectbox("Tipo de máquina", options=machine_type_opts)
    type_label_to_key = {v: k for k, v in MACHINE_TYPE_LABELS.items()}
    selected_machine_type = type_label_to_key.get(selected_type_label)

with filter_col3:
    severity_filter = st.multiselect(
        "Severidad",
        options=SEVERITY_ORDER,
        default=SEVERITY_ORDER,
        format_func=lambda s: SEVERITY_LABELS.get(s, s),
    )

with filter_col4:
    pattern_opts = list(PATTERN_INFO.keys())
    # Patrón and Severidad are independent filters: a pattern like
    # NEW_WEEKLY_MAX can resolve to different severities per row (see
    # resolve_pattern_info), so its default selection here can't depend on
    # severity_filter the way it used to -- all patterns are pre-checked,
    # and Severidad below does the actual severity-based row filtering.
    selected_patterns = st.multiselect(
        "Patrón",
        options=pattern_opts,
        default=pattern_opts,
        format_func=lambda p: f"{PATTERN_INFO[p]['icon']} {PATTERN_INFO[p]['label']}",
    )

# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------
try:
    df = await load_anomaly_events(days_back=int(days_back), machine_type=selected_machine_type)
except Exception as e:
    st.error(f"Error consultando eventos de CDF: {e}")
    df = None

if df is not None and not df.empty:
    df["severity"] = df.apply(
        lambda r: resolve_pattern_info(r["pattern"], r.get("timeseries_label")).get("severity"), axis=1
    )
    df = df[df["severity"].isin(severity_filter)]

if df is not None and not df.empty and selected_patterns:
    df = df[df["pattern"].isin(selected_patterns)]
elif df is not None and not selected_patterns:
    df = df.iloc[0:0]

machine_codes_available = sorted(df["machine_code"].unique().tolist()) if df is not None and not df.empty else []
selected_machine_code = st.selectbox("Máquina (opcional)", options=["Todas"] + machine_codes_available)
if df is not None and not df.empty and selected_machine_code != "Todas":
    df = df[df["machine_code"] == selected_machine_code]

# ---------------------------------------------------------
# Summary counters
# ---------------------------------------------------------
st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
summary_cols = st.columns(len(SEVERITY_ORDER) + 1)
total_count = 0 if df is None else len(df)
summary_cols[0].metric("Total", total_count)
for i, sev in enumerate(SEVERITY_ORDER, start=1):
    count = 0
    if df is not None and not df.empty:
        count = (df["severity"] == sev).sum()
    summary_cols[i].metric(SEVERITY_LABELS[sev], count)

st.markdown("---")

# ---------------------------------------------------------
# Scrolling event feed
# ---------------------------------------------------------
def _fmt_num(v):
    if v is None or v == "":
        return None
    try:
        return f"{float(v):,.0f}"
    except (ValueError, TypeError):
        return str(v)


def render_event_card(row) -> str:
    info = resolve_pattern_info(row["pattern"], row.get("timeseries_label"))

    meta_parts = []
    if row.get("value_before") is not None and row.get("value_after") is not None:
        meta_parts.append(f"Antes: {_fmt_num(row['value_before'])} &rarr; Después: {_fmt_num(row['value_after'])}")
    if row.get("current_value") is not None and row.get("baseline_avg") is not None:
        meta_parts.append(f"Valor actual: {_fmt_num(row['current_value'])} | Mediana: {_fmt_num(row['baseline_avg'])}")
    if row.get("current_value") is not None and row.get("baseline_max") is not None:
        meta_parts.append(f"Valor actual: {_fmt_num(row['current_value'])} | Máximo anterior: {_fmt_num(row['baseline_max'])}")
    if row.get("shift"):
        meta_parts.append(f"Turno: {html.escape(str(row['shift']))}")
    meta_line = " &nbsp;|&nbsp; ".join(meta_parts)

    desc = html.escape(str(row.get("description", "")))
    machine_code = html.escape(str(row.get("machine_code", "")))
    ts_label = html.escape(str(row.get("timeseries_label", "")))

    return f"""
    <div class="event-card" style="border-left-color:{info['color']}; background-color:{info['bg']};">
        <div class="event-header">
            <span class="event-title">{info['icon']} {html.escape(info['label'])} &mdash; {machine_code}
                <span style="font-weight:400; color:#6b7280;">({ts_label})</span>
            </span>
            <span class="event-time">{row.get('start_time_local', '')}</span>
        </div>
        <div class="event-desc">{desc}</div>
        <div class="event-meta">{meta_line}</div>
    </div>
    """


if df is None:
    pass
elif df.empty:
    st.info("No se encontraron anomalías con los filtros seleccionados.")
else:
    feed_html = "".join(render_event_card(row) for _, row in df.iterrows())
    st.markdown(feed_html, unsafe_allow_html=True)
