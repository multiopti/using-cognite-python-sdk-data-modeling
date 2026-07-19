import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os

# 1. Full-width screen configuration
st.set_page_config(page_title="Reporte de producción", layout="wide")

# App Title
st.title("Reporte de producción")

CSV_FILENAME = "simulated_1week_data_printer.csv"

# 2. Data loading function
@st.cache_data
def load_data():
    if os.path.exists(CSV_FILENAME):
        df = pd.read_csv(CSV_FILENAME)
    else:
        # Emergency generation fallback if script is executed standalone
        dates = pd.date_range(start='2026-07-12', end='2026-07-19', freq='D')
        printers = ['L1', 'L31', 'L32']
        shifts = ['5AM-5PM', '5PM-5AM']
        hours = ["5 a 6", "6 a 7", "7 a 8", "8 a 9", "9 a 10", "10 a 11", "11 a 12", "12 a 1", "1 a 2", "2 a 3", "3 a 4", "4 a 5"]
        base_prod = [45000, 55000, 58000, 60000, 61200, 59800, 60500, 56400, 60100, 61500, 59700, 60400]
        base_retrac = [23, 0, 2, 5, 3, 5, 4, 35, 10, 11, 6, 6]
        base_blow = [23, 3, 4, 6, 7, 4, 22, 12, 5, 7, 8, 3]
        rows = []
        np.random.seed(42)
        for date in dates:
            for printer in printers:
                for shift in shifts:
                    for i, hour in enumerate(hours):
                        prod = max(0, base_prod[i] + int(np.random.normal(0, 1200)))
                        retrac = max(0, base_retrac[i] + np.random.randint(-2, 4))
                        blow = max(0, base_blow[i] + np.random.randint(-2, 3))
                        rows.append({
                            'Fecha': date.strftime('%Y-%m-%d'), 'Printer': printer, 'Shift': shift, 'Hora': hour,
                            'Producción x hora': prod, 'Retrac-x-hora': retrac, 'Blow of': blow
                        })
        df = pd.DataFrame(rows)
    
    if 'Shift' in df.columns:
        df = df.rename(columns={'Shift': 'Turno'})
    return df

df = load_data()

# 3. Form-controlled Filters to prevent automatic refreshing on every click
with st.form("filtros_reporte"):
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        selected_fecha = st.selectbox("Fecha", options=sorted(df['Fecha'].unique()))
        
    with filter_col2:
        selected_printer = st.selectbox("Printer", options=sorted(df['Printer'].unique()))
        
    with filter_col3:
        selected_turno = st.selectbox("Turno", options=df['Turno'].unique())
        
    # The submission button that triggers data processing
    submitted = st.form_submit_button("Actualizar", type="primary")

# 4. Filter and sort timeline logically
filtered_df = df[
    (df['Fecha'] == selected_fecha) & 
    (df['Printer'] == selected_printer) & 
    (df['Turno'] == selected_turno)
].copy()

hour_order = ["5 a 6", "6 a 7", "7 a 8", "8 a 9", "9 a 10", "10 a 11", "11 a 12", "12 a 1", "1 a 2", "2 a 3", "3 a 4", "4 a 5"]
filtered_df['Hora'] = pd.Categorical(filtered_df['Hora'], categories=hour_order, ordered=True)
filtered_df = filtered_df.sort_values('Hora')

# 5. Render Chart and Metrics
if not filtered_df.empty:
    fig = px.line(
        filtered_df, 
        x='Hora', 
        y='Producción x hora', 
        markers=True,
        labels={'Producción x hora': 'Producción (unidades)', 'Hora': 'Intervalo de Hora'},
        title=f"Producción por Hora: {selected_printer} — {selected_turno} ({selected_fecha})"
    )
    
    # Reduced height to 275 (half of 550) for compact layout view
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
        yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
        height=275,
        title_font=dict(size=14),
        margin=dict(t=40, b=40, l=40, r=40)
    )
    
    fig.update_traces(
        line=dict(color='#0078D4', width=3), 
        marker=dict(size=8, color='#E81123', symbol='circle')
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Dynamic KPI Summary Cards below the chart
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("Producción Total", f"{filtered_df['Producción x hora'].sum():,} uds")
    m2.metric("Desperdicio Total (Retrac)", f"{filtered_df['Retrac-x-hora'].sum():,}")
    m3.metric("Fallas de soplado (Blow of)", f"{filtered_df['Blow of'].sum():,}")
else:
    st.warning("No se encontraron registros coincidentes.")