import streamlit as st

# OBLIGATORIO: debe ser el primer comando de Streamlit que se ejecute
st.set_page_config(page_title="Línea 1 - Vista de Planta", layout="wide")

import asyncio
import base64
import io
from datetime import datetime

import plotly.graph_objects as go

from config import (
    BASE_FIGURE_HEIGHT,
    CUSTOM_CSS,
    DI_COLUMN_X,
    DI_MACHINE_CODES,
    DI_NUMBER_BOX_HEIGHT,
    DI_NUMBER_BOX_WIDTH,
    DI_ROW_Y,
    DI_VALUE_BOX_HEIGHT,
    DI_VALUE_BOX_WIDTH,
    ELEMENT_COLORS,
    ELEMENT_HEIGHT,
    ELEMENT_WIDTH,
    ELEMENTS,
    ISPRAY_COLUMN_X,
    ISPRAY_LABEL,
    ISPRAY_MACHINE_CODES,
    ISPRAY_ROW_Y,
    ISPRAY_VALUE_BOX_WIDTH,
    LOCAL_TZ,
    LOGO_B64,
    MINSTER_TARGET,
    MINSTER_X,
    MINSTER_Y,
    PLANT_IMAGE_B64,
    PLANT_IMAGE_HEIGHT,
    PLANT_IMAGE_WIDTH,
    PLOT_Y_MAX,
    PLOT_Y_MIN,
    current_shift_label,
)
from cdf_service import load_line1_values, load_machine_values

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
    values, di_values, ispray_values = await asyncio.gather(
        load_line1_values(),
        load_machine_values(DI_MACHINE_CODES),
        load_machine_values(ISPRAY_MACHINE_CODES),
    )
except Exception as e:
    st.error(f"Error consultando datos de CDF: {e}")
    values, di_values, ispray_values = {}, {}, {}

# ---------------------------------------------------------
# Plant diagram with live values overlaid, mirroring the Grafana
# "Producción - Línea 1" canvas panel (grafana/dashboard_linea1.json).
# ---------------------------------------------------------
fig = go.Figure()

fig.add_layout_image(
    dict(
        source="data:image/jpeg;base64," + PLANT_IMAGE_B64,
        xref="x", yref="y",
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
        xref="x", yref="y",
        text=f"<b>{text}</b>",
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

# MINSTER: below the image, under the "MINSTER" text baked into the photo
# (see config.py's comment on MINSTER_X/Y for why it moved out of the
# image).
minster_raw = values.get(MINSTER_TARGET)
minster_text = f"{minster_raw:,.0f}" if minster_raw is not None else "--"
minster_colors = ELEMENT_COLORS["production"]
fig.add_annotation(
    x=MINSTER_X, y=MINSTER_Y,
    xref="x", yref="y",
    text=f"<b>{minster_text}</b>",
    showarrow=False,
    align="center",
    font=dict(size=13, color="#000000"),
    bgcolor=minster_colors["bg"],
    bordercolor=minster_colors["border"],
    borderwidth=1.5,
    borderpad=6,
    width=ELEMENT_WIDTH,
    height=ELEMENT_HEIGHT,
)


def add_machine_columns(codes, xs, row_y, machine_values, value_box_width):
    """One column per physical machine (no line-level target -- see
    cdf_service.load_machine_values), stacking unlabeled boxes: machine
    number on top, then one box per value row present in row_y
    ("production", and "scrap" only for machine types that track it)."""
    for code, x in zip(codes, xs):
        machine_no = "".join(ch for ch in code if ch.isdigit())  # "DI11" -> "11", "ISPRAY13" -> "13"
        totals = machine_values.get(code, {})
        rows = [(row_y["number"], "neutral", machine_no, DI_NUMBER_BOX_WIDTH, DI_NUMBER_BOX_HEIGHT)]
        for kind in ("production", "scrap"):
            if kind in row_y:
                value = totals.get(kind)
                text = f"{value:,.0f}" if value is not None else "--"
                rows.append((row_y[kind], kind, text, value_box_width, DI_VALUE_BOX_HEIGHT))
        for y, kind, text, box_width, box_height in rows:
            colors = ELEMENT_COLORS[kind]
            fig.add_annotation(
                x=x, y=y,
                xref="x", yref="y",
                text=f"<b>{text}</b>",
                showarrow=False,
                align="center",
                font=dict(size=12, color="#000000"),
                bgcolor=colors["bg"],
                bordercolor=colors["border"],
                borderwidth=1.5,
                borderpad=4,
                width=box_width,
                height=box_height,
            )


# D&I: number / Producción / Merma, below the image alongside MINSTER.
add_machine_columns(DI_MACHINE_CODES, DI_COLUMN_X, DI_ROW_Y, di_values, DI_VALUE_BOX_WIDTH)
# ISPRAY: number / Producción (no scrap tracked), in the black band above the
# ISPRAY conveyor, with its caption right above the boxes.
add_machine_columns(ISPRAY_MACHINE_CODES, ISPRAY_COLUMN_X, ISPRAY_ROW_Y, ispray_values, ISPRAY_VALUE_BOX_WIDTH)
fig.add_annotation(
    x=ISPRAY_LABEL["x"], y=ISPRAY_LABEL["y"],
    xref="x", yref="y",
    text=ISPRAY_LABEL["text"],
    showarrow=False,
    font=dict(family="Arial, sans-serif", size=ISPRAY_LABEL["size"], color=ISPRAY_LABEL["color"]),
)

# Axes are locked to the image: autorange=False + fixedrange=True so neither
# Plotly's autoscale nor a zoom/double-click can ever switch to auto-ranging.
# With no data traces, autorange sizes the axes around the fixed-pixel
# annotations instead of the image, which shrinks the diagram to nothing and
# piles every box on top of each other.
fig.update_xaxes(visible=False, range=[0, 1], autorange=False, fixedrange=True)
fig.update_yaxes(
    visible=False, range=[PLOT_Y_MIN, PLOT_Y_MAX], autorange=False, fixedrange=True,
    scaleanchor="x", scaleratio=PLANT_IMAGE_HEIGHT / PLANT_IMAGE_WIDTH,
)
fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    height=round(BASE_FIGURE_HEIGHT * (PLOT_Y_MAX - PLOT_Y_MIN)),
    plot_bgcolor="black",
    paper_bgcolor="black",
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": False, "doubleClick": False, "scrollZoom": False},
)

st.markdown(
    f"<div style='color:#9ca3af; font-size:12px; margin-top:8px;'>"
    f"Valores del turno en curso &middot; actualizado {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}"
    f"</div>",
    unsafe_allow_html=True,
)

if st.button("Actualizar"):
    st.rerun()
