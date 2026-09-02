import streamlit as st

# OBLIGATORIO: debe ser el primer comando de Streamlit que se ejecute
st.set_page_config(page_title="Dashboard General de Producción", layout="wide")

import html

import pandas as pd

from config import (
    CUSTOM_CSS,
    FLOW_ORDER,
    LINES,
    LOGO_URL,
    STATUS_COLORS,
    STATUS_LABELS,
    TYPE_COLORS,
    TYPE_LABELS,
    thirty_days_ago_str,
    today_str,
)
from cdf_service import all_machine_codes, load_overview
from charts import render_efficiency_gauge, render_type_bar_chart

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

header_col1, header_col2 = st.columns([3, 2])

with header_col1:
    try:
        st.image(LOGO_URL, width=130)
    except Exception:
        pass
    st.markdown("<h1 class='custom-title'>Dashboard General de Producción</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div style='color:#6b7280; margin-bottom:6px;'>Todas las máquinas &middot; Línea 1 y Línea 3</div>",
        unsafe_allow_html=True,
    )

with header_col2:
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        fecha = st.date_input(
            "Fecha",
            value=pd.to_datetime(today_str()).date(),
            min_value=pd.to_datetime(thirty_days_ago_str()).date(),
            max_value=pd.to_datetime(today_str()).date(),
            key="input_fecha",
        )
    with filter_col2:
        turno_opts = ["6AM-6PM", "6PM-6AM"]
        turno = st.selectbox("Turno", options=turno_opts, key="input_turno")

fecha_str = fecha.strftime("%Y-%m-%d")

# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------
try:
    df = await load_overview(fecha_str, turno)
except Exception as e:
    st.error(f"Error consultando eventos de CDF: {e}")
    df = pd.DataFrame()

st.markdown("<hr style='margin-top:8px; margin-bottom:20px;' />", unsafe_allow_html=True)

if df.empty:
    st.info("No se encontraron reportes de producción para esta fecha y turno.")
else:
    # -------------------------------------------------------
    # KPIs
    # -------------------------------------------------------
    active_hours = df[df["hourly_production"] > 0]
    avg_efficiency = float(active_hours["pct_eficiencia"].mean()) if not active_hours.empty else 0.0

    total_machines = len(all_machine_codes())
    latest_per_machine = df.sort_values("entry_slot").groupby("machine_code", as_index=False).last()
    machines_active = int((latest_per_machine["hourly_production"] > 0).sum())

    total_downtime = float(df["downtime_min"].sum())
    total_scrap = float(df["scrap"].sum())

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Eficiencia Global", f"{avg_efficiency:.1f}%", help="Meta: 85%")
    kpi_cols[1].metric("Máquinas Activas", f"{machines_active} / {total_machines}")
    kpi_cols[2].metric("Tiempo de Parada Total", f"{total_downtime:,.0f} min".replace(",", "."))
    kpi_cols[3].metric("Eventos de Merma", f"{total_scrap:,.0f}".replace(",", "."))

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------
    # Line panels
    # -------------------------------------------------------
    def render_line_panel(line_name: str):
        groups = LINES[line_name]
        flow = FLOW_ORDER[line_name]
        line_df = df[df["line"] == line_name]
        machine_count = sum(len(codes) for codes in groups.values())

        st.markdown(
            f"<div class='line-panel-title'>{html.escape(line_name)}</div>"
            f"<div class='line-panel-sub'>{machine_count} máquinas &middot; "
            f"{' &middot; '.join(TYPE_LABELS[t] for t in flow)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

        gauge_col, bar_col = st.columns([1, 2])

        line_active = line_df[line_df["hourly_production"] > 0]
        line_eff = float(line_active["pct_eficiencia"].mean()) if not line_active.empty else 0.0
        with gauge_col:
            st.plotly_chart(
                render_efficiency_gauge(line_eff, TYPE_COLORS["minster"], f"Eficiencia {line_name}"),
                use_container_width=True,
            )

        with bar_col:
            labels = [TYPE_LABELS[t] for t in flow]
            colors = [TYPE_COLORS[t] for t in flow]
            values = [float(line_df[line_df["machine_type"] == t]["hourly_production"].sum()) for t in flow]
            st.plotly_chart(render_type_bar_chart(labels, values, colors), use_container_width=True)

        st.markdown("<div style='font-size:12px; color:#6b7280; margin:10px 0 6px 0;'>Estado de máquinas</div>", unsafe_allow_html=True)

        pills = []
        for m_type in flow:
            for code in groups[m_type]:
                machine_rows = line_df[line_df["machine_code"] == code]
                if machine_rows.empty:
                    status = "no_data"
                else:
                    latest = machine_rows.sort_values("entry_slot").iloc[-1]
                    if latest["hourly_production"] > 0:
                        status = "running"
                    elif "falla" in str(latest["observations"]).lower():
                        status = "failure"
                    else:
                        status = "idle"
                color = STATUS_COLORS[status]
                label = STATUS_LABELS[status]
                pills.append(
                    f"<span class='status-pill' title='{html.escape(label)}'>"
                    f"<span class='status-dot' style='background:{color};'></span>{html.escape(code)}</span>"
                )
        st.markdown("".join(pills), unsafe_allow_html=True)

    panel_col1, panel_col2 = st.columns(2)
    with panel_col1:
        st.markdown("<div class='line-panel'>", unsafe_allow_html=True)
        render_line_panel("Línea 1")
        st.markdown("</div>", unsafe_allow_html=True)
    with panel_col2:
        st.markdown("<div class='line-panel'>", unsafe_allow_html=True)
        render_line_panel("Línea 3")
        st.markdown("</div>", unsafe_allow_html=True)
