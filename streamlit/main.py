import streamlit as st

# ⚠️ OBLIGATORIO: Debe ser el primer comando de Streamlit que se ejecute
st.set_page_config(page_title="Reporte de Producción", layout="wide")

import asyncio
from datetime import date, timedelta
import pandas as pd
from cognite.client.data_classes.capabilities import EventsAcl

# Las importaciones locales van DESPUÉS de set_page_config
from config import (
    MACHINE_GROUPS, DAY_HOURS, NIGHT_HOURS,
    INCIDENTES_OPCIONES, LOGO_URL, CUSTOM_CSS,
    get_display_columns
)
from cdf_service import (
    load_shift_report_from_cdf,
    save_observations_to_cdf,
    fetch_heartbeat_status,
    client,
)
from charts import render_machine_charts, render_gauges

# ---------------------------------------------------------
# 1. Custom CSS
# ---------------------------------------------------------
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Top Logo
# ---------------------------------------------------------
try:
    st.image(LOGO_URL, width=130)
except Exception:
    pass

# ---------------------------------------------------------
# 3. State Initialization & Filter Callback
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


async def user_can_edit_reports(client) -> bool:
    """
    Determina si el usuario puede editar/guardar reportes, mirando su
    capability EFECTIVA sobre Events (EventsAcl: WRITE), no la pertenencia a
    un grupo por nombre.

    Por qué el cambio: en CDF los permisos de un usuario son la UNIÓN de
    TODOS los grupos a los que pertenece. Un usuario puede estar en
    'FTDM-Grp-ViewApp' (pensado como solo-lectura) y AL MISMO TIEMPO en otro
    grupo que sí le da permiso de escritura -- si solo se comprueba "¿está en
    el grupo de solo lectura?" ese usuario queda bloqueado incorrectamente,
    aunque su capability real (la más alta entre todos sus grupos) sí
    permita guardar. client.iam.token.inspect().capabilities ya viene
    resuelto/agregado por CDF a partir de todos los grupos del usuario, así
    que comprobar la capability ahí evita ese problema por construcción.

    Nota: esto comprueba si existe ALGÚN EventsAcl con acción WRITE (con
    scope "todo" o "por dataset"), sin verificar el dataset específico que
    usa save_observations_to_cdf. Si en el futuro los eventos de este reporte
    quedan acotados a un dataset concreto, conviene refinar esta función para
    comprobar ese scope exacto en vez de "cualquier WRITE sobre eventos".

    Devuelve True si el usuario PUEDE editar y guardar. Ante cualquier fallo
    (red, permisos, forma de respuesta inesperada) se asume que NO puede
    editar (False), por seguridad.
    """
    try:
        inspection = await client.iam.token.inspect()

        for project_capability in inspection.capabilities:
            capability = project_capability.capability
            if isinstance(capability, EventsAcl) and EventsAcl.Action.Write in capability.actions:
                return True

        return False
    except Exception as e:
        st.warning(f"No se pudo verificar los permisos del usuario: {e}")
        # Por seguridad, si falla la verificación asumimos que NO puede editar
        return False


# ---------------------------------------------------------
# 4. Operational Filter Bar
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
        "Tipo de Máquina",
        options=list(MACHINE_GROUPS.keys()),
        index=list(MACHINE_GROUPS.keys()).index(active_m_type) if active_m_type in MACHINE_GROUPS else 0,
        key="input_m_type"
    )

with filter_col3:
    available_machines = MACHINE_GROUPS.get(selected_m_type, list(MACHINE_GROUPS.values())[0])
    m_index = available_machines.index(active_machine_label) if active_machine_label in available_machines else 0
    st.selectbox(
        "Máquina",
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
    st.button("Actualizar 🔄", use_container_width=True, on_click=apply_filters_callback)

# ---------------------------------------------------------
# 5. Main Report Title
# ---------------------------------------------------------
st.markdown(
    f"<h1 class='custom-title'>Reporte de Producción: {active_m_type} ({active_machine_label})</h1>",
    unsafe_allow_html=True
)
st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 6. CDF Load Logic
# ---------------------------------------------------------
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
# 7. Merge Timeline with Event Data
# ---------------------------------------------------------
active_hours = DAY_HOURS if active_turno == "5AM-5PM" else NIGHT_HOURS
full_shift_df = pd.DataFrame({"Slot": list(range(1, 13)), "Hora": active_hours})

if not existing_df.empty:
    if 'Hora' in existing_df.columns:
        existing_df = existing_df.drop(columns=['Hora'])
    filtered_df = pd.merge(full_shift_df, existing_df, on="Slot", how="left")
else:
    filtered_df = full_shift_df.copy()

if active_m_type == "PRINTER":
    num_cols = ['Producción x hora', 'Retrac-x-hora', 'Blow of', 'Tiempo de parada']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operación estándar'}
elif active_m_type == "MINSTER":
    num_cols = ['Golpes Bobina', 'Golpes Turno', 'Tiempo Parada (min)']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operación estándar'}
elif active_m_type == "ISPRAY":
    num_cols = ['Producción x hora', 'Tiempo Parada (min)']
    str_cols = {'% Eficiencia': '0.00%', 'Observaciones': 'Operación estándar'}
else:
    num_cols = [
        'PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER',
        'LAT x LAT CORTAS', 'LAT x TRANC TRIM',
        'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
        'Tiempo parada (min)', 'Merma (kg)'
    ]
    str_cols = {'% Merma': '0.00%', '% Eficiencia': '0.00%', 'Observaciones': 'Operación estándar'}

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

# ---------------------------------------------------------
# 8. Render Visualizations
# ---------------------------------------------------------
render_machine_charts(filtered_df, active_m_type, active_machine_label, active_turno)
render_gauges(filtered_df, active_m_type)

# ---------------------------------------------------------
# 9. Format Display Table & Interactive Data Editor
# ---------------------------------------------------------
st.markdown("### Detalle Horario del Turno")

table_display_cols = get_display_columns(active_m_type)
display_df = filtered_df[table_display_cols].copy()

if active_m_type == "PRINTER":
    for int_col in ['Producción x hora', 'Retrac-x-hora', 'Blow of']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo de parada'] = display_df['Tiempo de parada'].apply(lambda x: f"{float(x):.2f}")

elif active_m_type == "MINSTER":
    for int_col in ['Golpes Bobina', 'Golpes Turno']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo Parada (min)'] = display_df['Tiempo Parada (min)'].apply(lambda x: f"{float(x):.2f}")

elif active_m_type == "ISPRAY":
    display_df['Producción x hora'] = display_df['Producción x hora'].apply(lambda x: f"{int(round(float(x)))}")
    display_df['Tiempo Parada (min)'] = display_df['Tiempo Parada (min)'].apply(lambda x: f"{float(x):.2f}")

else:
    for int_col in ['PROD. LATAS', 'LAT CORTAS', 'TRANC TRIMMER', 'LAT x LAT CORTAS', 'LAT x TRANC TRIM']:
        display_df[int_col] = display_df[int_col].apply(lambda x: f"{int(round(float(x)))}")
    for float_col in [
        'Tiempo prom de parada x lat cort (min)', 'Tiempo prom de parada x tranc trim (min)',
        'Tiempo parada (min)', 'Merma (kg)'
    ]:
        display_df[float_col] = display_df[float_col].apply(lambda x: f"{float(x):.2f}")

# Verifica los permisos del usuario una sola vez por sesión (evita repetir
# la llamada a CDF -- token.inspect() -- en cada rerun que dispara Streamlit
# al tocar cualquier widget).
if "user_can_edit" not in st.session_state:
    st.session_state.user_can_edit = await user_can_edit_reports(client)
user_can_edit = st.session_state.user_can_edit

display_df = display_df.astype(str)

obs_existentes = [obs for obs in display_df['Observaciones'].unique().tolist() if obs]
opciones_desplegable = list(dict.fromkeys(INCIDENTES_OPCIONES + obs_existentes))

# ---------------------------------------------------------
# Control de Permisos en la Tabla
# ---------------------------------------------------------
if user_can_edit:
    read_only_cols = [c for c in display_df.columns if c != 'Observaciones']
else:
    read_only_cols = True  # Bloquea toda la tabla (incluyendo 'Observaciones')

edited_df = st.data_editor(
    display_df,
    column_config={
        "Observaciones": st.column_config.SelectboxColumn(
            "Observaciones / Incidencias",
            help="Seleccione la falla o evento principal ocurrido en el bloque horario" if user_can_edit else "Modo de solo lectura -- tu usuario no tiene permiso de escritura sobre eventos",
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
# 10. Save Button Section
# ---------------------------------------------------------


st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
btn_save_col1, btn_save_col2 = st.columns([2.5, 5])

if user_can_edit:
    # --- AUTHORIZED EDITORS: Display Save Button ---
    with btn_save_col1:
        if st.button("Guardar Cambios 💾", use_container_width=True):
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
                    st.success(f"¡{total_mod} registro(s) actualizados correctamente en CDF! 🎉")
                else:
                    st.info("No se detectaron cambios pendientes por guardar.")
            except Exception as e:
                st.error(f"Error al guardar los cambios en CDF: {e}")
else:
    # --- READ-ONLY USER: Hide Button & Display Notice ---
    with btn_save_col1:
        st.info("🔒 **Modo Vista:** Tu usuario no tiene permiso de escritura sobre eventos y no puede guardar observaciones.")


# ---------------------------------------------------------
# 11. Edge Heartbeat Footer
# ---------------------------------------------------------
heartbeat_val = await fetch_heartbeat_status()
st.markdown(f"**Last Heartbeat:** {heartbeat_val}")
