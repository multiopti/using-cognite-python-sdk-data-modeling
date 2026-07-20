import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Full-width screen configuration
st.set_page_config(page_title="Reporte de producción", layout="wide")

# Custom CSS to safely adjust layout margins without clipping headers
st.markdown("""
    <style>
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 1rem !important;
    }
    .custom-title {
        margin-top: 0px !important;
        margin-bottom: 20px !important;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

# App Title
st.markdown("<h1 class='custom-title'>Reporte de producción</h1>", unsafe_allow_html=True)

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

# 3. Form-controlled Filters
with st.form("filtros_reporte"):
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        selected_fecha = st.selectbox("Fecha", options=sorted(df['Fecha'].unique()))
        
    with filter_col2:
        selected_printer = st.selectbox("Printer", options=sorted(df['Printer'].unique()))
        
    with filter_col3:
        selected_turno = st.selectbox("Turno", options=df['Turno'].unique())
        
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

# 5. Render Line Chart
if not filtered_df.empty:
    fig_line = px.line(
        filtered_df, 
        x='Hora', 
        y='Producción x hora', 
        markers=True,
        labels={'Producción x hora': 'Producción (unidades)', 'Hora': 'Intervalo de Hora'},
        title=f"Producción por Hora: {selected_printer} — {selected_turno} ({selected_fecha})"
    )
    
    fig_line.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
        yaxis=dict(showgrid=True, gridcolor='#F0F0F0', linecolor='#333333'),
        height=250, 
        title_font=dict(size=14),
        margin=dict(t=35, b=25, l=40, r=40)
    )
    
    fig_line.update_traces(
        line=dict(color='#0078D4', width=3), 
        marker=dict(size=8, color='#E81123', symbol='circle')
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
    
    # 6. Calculate Totals and Downtime metrics
    total_prod = int(filtered_df['Producción x hora'].sum())
    total_retrac = int(filtered_df['Retrac-x-hora'].sum())
    total_blow = int(filtered_df['Blow of'].sum())
    
    # Calculate downtime per hour using formula: 60 - ((Prod * 60) / 66000)
    filtered_df['Tiempo de parada'] = 60 - ((filtered_df['Producción x hora'] * 60) / 66000)
    total_downtime = round(filtered_df['Tiempo de parada'].sum(), 1)
    
    # 7. Render 4 Gauges Side-by-Side
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 5px;' />", unsafe_allow_html=True)
    gauge_col1, gauge_col2, gauge_col3, gauge_col4 = st.columns(4)
    
    # Gauge 1: Producción Total
    with gauge_col1:
        fig_prod = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total_prod,
            title={'text': "Producción Total (Turno)", 'font': {'size': 13}},
            gauge={
                'axis': {
                    'range': [0, 720000], 
                    'tickvals': [0, 200000, 400000, 600000, 720000],
                    'ticktext': ['0', '200k', '400k', '600k', '720k'],
                    'tickfont': {'size': 10}
                },
                'bar': {'color': "#0078D4"},
                'steps': [
                    {'range': [0, 396000], 'color': "#FFCCCC"},
                    {'range': [396000, 720000], 'color': "#E6E6E6"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 3},
                    'thickness': 0.75,
                    'value': 396000
                }
            }
        ))
        fig_prod.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_prod, use_container_width=True)
        
    # Gauge 2: Retrac Total
    with gauge_col2:
        fig_retrac = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total_retrac,
            title={'text': "Retrac Total", 'font': {'size': 13}},
            gauge={
                'axis': {'range': [0, 1000], 'tickwidth': 1, 'tickfont': {'size': 10}},
                'bar': {'color': "#2B579A"},
                'steps': [
                    {'range': [0, 800], 'color': "#E6E6E6"},
                    {'range': [800, 1000], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 3},
                    'thickness': 0.75,
                    'value': 800
                }
            }
        ))
        fig_retrac.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_retrac, use_container_width=True)

    # Gauge 3: Blow of Total
    with gauge_col3:
        fig_blow = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total_blow,
            title={'text': "Blow of Total", 'font': {'size': 13}},
            gauge={
                'axis': {'range': [0, 1000], 'tickwidth': 1, 'tickfont': {'size': 10}},
                'bar': {'color': "#2B579A"},
                'steps': [
                    {'range': [0, 800], 'color': "#E6E6E6"},
                    {'range': [800, 1000], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 3},
                    'thickness': 0.75,
                    'value': 800
                }
            }
        ))
        fig_blow.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_blow, use_container_width=True)

    # Gauge 4: Tiempo de Parada Total (0 to 720 min, over 360 min is red zone)
    with gauge_col4:
        fig_stop = go.Figure(go.Indicator(
            mode="gauge+number",
            value=total_downtime,
            number={'suffix': ' min'},
            title={'text': "Tiempo Parada Total", 'font': {'size': 13}},
            gauge={
                'axis': {'range': [0, 720], 'tickwidth': 1, 'tickfont': {'size': 10}},
                'bar': {'color': "#515151"},
                'steps': [
                    {'range': [0, 360], 'color': "#E6E6E6"},
                    {'range': [360, 720], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 3},
                    'thickness': 0.75,
                    'value': 360
                }
            }
        ))
        fig_stop.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
        st.plotly_chart(fig_stop, use_container_width=True)

else:
    st.warning("No se encontraron registros coincidentes.")