import streamlit as st

# OBLIGATORIO: debe ser el primer comando de Streamlit que se ejecute
st.set_page_config(page_title="Línea 1 - Vista de Planta", layout="wide")

import base64
import io
from datetime import datetime

import plotly.graph_objects as go

from config import (
    CUSTOM_CSS,
    ELEMENT_COLORS,
    ELEMENT_HEIGHT,
    ELEMENT_WIDTH,
    ELEMENTS,
    LOCAL_TZ,
    LOGO_B64,
    PLANT_IMAGE_B64,
    current_shift_label,
)
from cdf_service import load_line1_values

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

try:
    st.image(io.BytesIO(base64.b64decode(LOGO_B64)), width=130)
except Exception:
    pass

st.markdown("<h1 class='custom-title'>Línea 1 - Vista de Planta</h1>", unsafe_allow_html=True)
st.markdown(
    f"<div style='color:#6b7280; margin-bottom:6px;'>MINSTER &middot; D&amp;I &middot; PRINTER &middot; ISPRAY "
    f"&mdash; {current_shift_label()}</div>",
    unsafe_allow_html=True,
)

try:
    values = await load_line1_values()
except Exception as e:
    st.error(f"Error consultando datos de CDF: {e}")
    values = {}

# ---------------------------------------------------------
# Plant diagram with live values overlaid, mirroring the Grafana
# "Producción - Línea 1" canvas panel (grafana/dashboard_linea1.json).
# ---------------------------------------------------------
fig = go.Figure()

fig.add_layout_image(
    dict(
        source="data:image/jpeg;base64," + PLANT_IMAGE_B64,
        xref="paper", yref="paper",
        x=0, y=1,
        sizex=1, sizey=1,
        xanchor="left", yanchor="top",
        sizing="stretch",
        layer="below",
    )
)

for el in ELEMENTS:
    raw = values.get(el["target"])
    text = f"{raw:,.0f}" if raw is not None else "--"
    colors = ELEMENT_COLORS[el["kind"]]
    fig.add_annotation(
        x=el["x"], y=1 - el["y"],
        xref="paper", yref="paper",
        text=f"<b>{el['label']}</b><br>{text}",
        showarrow=False,
        align="center",
        font=dict(size=13, color="#000000"),
        bgcolor=colors["bg"],
        bordercolor=colors["border"],
        borderwidth=1.5,
        borderpad=6,
        width=ELEMENT_WIDTH,
        height=ELEMENT_HEIGHT,
    )

fig.update_xaxes(visible=False, range=[0, 1])
fig.update_yaxes(visible=False, range=[0, 1], scaleanchor="x", scaleratio=966 / 1684)
fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    height=650,
    plot_bgcolor="black",
    paper_bgcolor="black",
)

st.plotly_chart(fig, use_container_width=True)

st.markdown(
    f"<div style='color:#9ca3af; font-size:12px; margin-top:8px;'>"
    f"Valores del turno en curso &middot; actualizado {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}"
    f"</div>",
    unsafe_allow_html=True,
)

if st.button("Actualizar"):
    st.rerun()
