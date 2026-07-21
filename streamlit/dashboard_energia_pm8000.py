import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuración de la página estilo profesional / industrial
st.set_page_config(
    page_title="PGO - Energy Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS modificado para centrar logo de forma agresiva y subir al máximo el contenido
st.markdown("""
    <style>
        /* Reducir el margen superior para subir todo el dashboard */
        .block-container {
            padding-top: 1rem !important; 
            padding-bottom: 1rem !important;
        }
        /* Eliminar por completo el padding superior de la barra lateral */
        [data-testid="stSidebarUserContent"] {
            padding-top: 0rem !important;
        }
        /* Forzar centrado absoluto del elemento img dentro del contenedor del sidebar */
        [data-testid="stSidebar"] [data-testid="stImage"] img {
            display: block !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        .main {
            background-color: #0e1117;
            color: #ffffff;
        }
        div[data-testid="stMetricValue"] {
            font-size: 28px;
            font-weight: bold;
            color: #00ffcc;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 14px;
            color: #a3a8b4;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #1f2937;
            border-radius: 4px;
            color: #ffffff;
            padding: 10px 20px;
        }
        .stTabs [data-baseweb="tab"] aria-selected="true" {
            background-color: #00ffcc;
            color: #000000;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GENERACIÓN DE DATOS SIMULADOS (MOCK DATA)
# ==========================================
@st.cache_data
def generate_pm8000_data():
    np.random.seed(42)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    time_index = pd.date_range(start=start_time, end=end_time, freq='1h')
    
    subestaciones_equipos = {
        "Subestación #1": [
            "Compresor NH3 #5", "Planta de recuperación de CO2 #2", "Caldera 2 y 3",
            "Bomba de Condensado 1", "Bomba de Condensado 2", "BAC #1,2,3",
            "Ventilador Torre de Enfriamiento", "Motor bomba 1 y 2 Torre de enfriamiento",
            "Iluminación sala de máquinas", "Planta Piloto", "CCM 1 Filtración",
            "CCM 2 Filtración", "CMF Filtración", "CCM Cocimiento", "CCM Molienda"
        ],
        "Subestación #2": [
            "Compresores NH3 #1,2,3 y 4", "Compresores de aire 1, 2 y", "Secador de aire #1",
            "Secador de aire #2", "Planta de CO2 #1", "Tablero Iluminación exterior"
        ],
        "Subestación #3": [
            "Tablero Pozo 1", "Tablero iluminación PTAR", "Bomba contra incendio",
            "Bomba de Soda Env", "Transformadores informatica", "Soplador 1,2y3",
            "CCM L1", "CCM L2", "Tablero iluminación envasado", "Iluminación despacho",
            "Tablero a/c oficinas", "Tablero aires acondicionados"
        ],
        "Subestación #4": [
            "Compresor de NH3 6,7 y 8", "Compresor de aire #4", "Secador de aire #2 y 3",
            "Planta de recuperación de CO2#3", "Planta de generación de CO2", "Caldera #4 y 5",
            "Bombas alimentación de calderas 4y5", "Bomba de condensado #3", "CCM Cocimientos #2",
            "Tablero servicios generales de cocimiento #2", "CCM Filtración 3+50 L3", "Tablero bombas de envasado"
        ],
        "Subestación #5": [
            "Alumbrado envasado", "Bomba contra incendios", "Informatica", "CCM L4, L5 y L6", "CCM PTAS"
        ],
        "Subestación #6": [
            "CCM L1 N/R,L3", "CCM PTAB", "Informatica"
        ],
        "Subestación #7": [
            "CCM L7"
        ],
        "Subestación #8": [
            "CCM L8"
        ]
    }
    
    data_list = []
    for subestacion, circuitos in subestaciones_equipos.items():
        for dt in time_index:
            hour = dt.hour
            is_weekend = dt.weekday() >= 5
            
            if 8 <= hour <= 18:
                factor_hora = 2.0 if not is_weekend else 1.2
            else:
                factor_hora = 1.0
                
            for circuit in circuitos:
                if 'Compresor' in circuit or 'CCM' in circuit or 'Caldera' in circuit:
                    base_load = np.random.randint(80, 250)
                else:
                    base_load = np.random.randint(10, 60)
                    
                kw = max(2, (base_load * factor_hora) + np.random.normal(0, 10))
                kvar = max(1, (kw * 0.3) + np.random.normal(0, 3))
                pf = min(1.0, max(0.80, 0.95 + np.random.normal(0, 0.03)))
                thd_v = max(0.5, min(5.0, 1.5 + (0.5 if hour in [11, 12, 16, 17] else 0) + np.random.normal(0, 0.2)))
                thd_i = max(1.0, min(15.0, 5.0 + (2.0 if hour in [11, 12, 16, 17] else 0) + np.random.normal(0, 0.8)))
                
                sag_event = 1 if np.random.rand() > 0.995 else 0
                swell_event = 1 if np.random.rand() > 0.998 else 0
                
                data_list.append({
                    'Timestamp': dt,
                    'Subestacion': subestacion,
                    'Circuito': circuit,
                    'Potencia_Activa_kW': round(kw, 2),
                    'Potencia_Reactiva_kVAR': round(kvar, 2),
                    'Factor_de_Potencia': round(pf, 3),
                    'THD_Voltaje_Porcentaje': round(thd_v, 2),
                    'THD_Corriente_Porcentaje': round(thd_i, 2),
                    'Sag_Event': sag_event,
                    'Swell_Event': swell_event,
                    'Energia_kWh': round(kw * 1.0, 2)
                })
            
    return pd.DataFrame(data_list)

df_data = generate_pm8000_data()

# ==========================================
# ESTRUCTURA DE LA INTERFAZ / SIDEBAR
# ==========================================

st.sidebar.image("logo regional.png", width=140)

st.sidebar.subheader("Métricas de Planta")

subestaciones_lista = sorted(df_data['Subestacion'].unique())
subestation_opt = st.sidebar.selectbox("Seleccione Subestación:", subestaciones_lista)

modelo_dashboard = st.sidebar.radio(
    "Modelo de Dashboard para Clientes:",
    [
        "🟢 Modelo 1: Gestión de Energía y Costos",
        "⚡ Modelo 2: Calidad de Energía y Diagnóstico Técnico",
        "📊 Modelo 3: Matriz de Demanda y Eficiencia Operativa"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Info del Medidor")
st.sidebar.info("""**Schneider EcoStruxure PM8000**
- Clase de Precisión: 0.2S
- Monitoreo de Calidad de Energía: IEC 61000-4-30 Clase S
- Registro de Eventos de Forma de Onda.""")

df_filtered = df_data[df_data['Subestacion'] == subestation_opt]

# TÍTULO DEL DASHBOARD Y SUBTÍTULO (CENTRADOS)
st.markdown(f"""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h1 style="margin-bottom: 0.2rem;">📊 Plataforma de Gestión de Operaciones (PGO)</h1>
        <h3 style="margin-top: 0rem; font-weight: normal; color: #ced4da;">
            Análisis Integral: {subestation_opt} | <span style="font-style: italic;">Medidores Serie PM8000</span>
        </h3>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# MODELO 1: GESTIÓN DE ENERGÍA Y COSTOS
# ==========================================
if "Modelo 1" in modelo_dashboard:
    st.markdown("#### 🟢 Modelo 1: Enfoque Financiero y Control de Consumo")
    
    total_kwh = df_filtered['Energia_kWh'].sum()
    costo_estimado = total_kwh * 0.12
    max_demanda = df_filtered.groupby('Timestamp')['Potencia_Activa_kW'].sum().max()
    fp_promedio = df_filtered['Factor_de_Potencia'].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Consumo Total Semanal", value=f"{total_kwh:,.1f} kWh")
    with col2:
        st.metric(label="Costo Eléctrico Estimado", value=f"${costo_estimado:,.2f}", delta="-2.1% vs semana anterior")
    with col3:
        st.metric(label="Pico de Demanda (Subestación)", value=f"{max_demanda:,.1f} kW")
    with col4:
        st.metric(label="Factor de Potencia Promedio", value=f"{fp_promedio:.3f}", delta="Óptimo" if fp_promedio >= 0.92 else "Penalidad Riesgo", delta_color="normal" if fp_promedio >= 0.92 else "inverse")

    st.markdown("---")
    
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("⚡ Demanda Horaria por Equipos (Top 10)")
        top_circuitos = df_filtered.groupby('Circuito')['Energia_kWh'].sum().nlargest(10).index
        df_top = df_filtered[df_filtered['Circuito'].isin(top_circuitos)]
        
        df_hourly = df_top.groupby(['Timestamp', 'Circuito'])['Potencia_Activa_kW'].sum().reset_index()
        fig_hourly = px.bar(
            df_hourly, x='Timestamp', y='Potencia_Activa_kW', color='Circuito',
            template='plotly_dark', color_discrete_sequence=px.colors.qualitative.Pastel,
            labels={'Potencia_Activa_kW': 'Potencia (kW)', 'Timestamp': 'Fecha y Hora'}
        )
        fig_hourly.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=340, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_hourly, use_container_width=True)
        
    with col_chart2:
        st.subheader("🥧 Distribución de Energía")
        df_pie = df_top.groupby('Circuito')['Energia_kWh'].sum().reset_index()
        fig_pie = px.pie(
            df_pie, values='Energia_kWh', names='Circuito', hole=0.4,
            template='plotly_dark', color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_pie.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=340, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# MODELO 2: CALIDAD DE ENERGÍA Y DIAGNÓSTICO
# ==========================================
elif "Modelo 2" in modelo_dashboard:
    st.markdown("#### ⚡ Modelo 2: Monitoreo Técnico y Calidad de Potencia (Power Quality)")
    
    total_sags = df_filtered['Sag_Event'].sum()
    total_swells = df_filtered['Swell_Event'].sum()
    avg_thd_v = df_filtered['THD_Voltaje_Porcentaje'].mean()
    avg_thd_i = df_filtered['THD_Corriente_Porcentaje'].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Huecos de Tensión (Sags)", value=int(total_sags), delta="Revisar" if total_sags > 0 else "Estable", delta_color="inverse" if total_sags > 0 else "normal")
    with col2:
        st.metric(label="Sobretensiones Transitorias", value=int(total_swells), delta="Crítico" if total_swells > 0 else "Estable", delta_color="inverse" if total_swells > 0 else "normal")
    with col3:
        st.metric(label="THD V (Promedio)", value=f"{avg_thd_v:.2f} %", delta="< 5% Norma" if avg_thd_v < 5 else "Riesgo", delta_color="normal" if avg_thd_v < 5 else "inverse")
    with col4:
        st.metric(label="THD I (Promedio)", value=f"{avg_thd_i:.2f} %")

    st.markdown("---")
    
    col_q1, col_q2 = st.columns(2)
    
    with col_q1:
        st.subheader("📊 Historial de Distorsión Armónica Global")
        df_thd_time = df_filtered.groupby('Timestamp')[['THD_Voltaje_Porcentaje', 'THD_Corriente_Porcentaje']].mean().reset_index()
        fig_thd = go.Figure()
        fig_thd.add_trace(go.Scatter(x=df_thd_time['Timestamp'], y=df_thd_time['THD_Voltaje_Porcentaje'], name='THD Voltaje (%)', line=dict(color='#00ffcc', width=2)))
        fig_thd.add_trace(go.Scatter(x=df_thd_time['Timestamp'], y=df_thd_time['THD_Corriente_Porcentaje'], name='THD Corriente (%)', line=dict(color='#ff9900', width=1.5, dash='dot')))
        fig_thd.update_layout(template='plotly_dark', height=340, margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig_thd, use_container_width=True)
        
    with col_q2:
        st.subheader("🎯 Factor de Potencia Crítico por Equipo")
        df_pf_circ = df_filtered.groupby('Circuito')['Factor_de_Potencia'].mean().nsmallest(10).reset_index()
        
        fig_pf = px.bar(
            df_pf_circ, x='Factor_de_Potencia', y='Circuito', orientation='h',
            template='plotly_dark', color='Factor_de_Potencia',
            color_continuous_scale=['#ff4d4d', '#ffcc00', '#00ffcc'],
            range_color=[0.80, 1.0]
        )
        fig_pf.add_vline(x=0.92, line_dash="dash", line_color="white", annotation_text="Límite Penalidad", annotation_position="top right")
        fig_pf.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=340)
        st.plotly_chart(fig_pf, use_container_width=True)

# ==========================================
# MODELO 3: MATRIZ DE DEMANDA Y EFICIENCIA
# ==========================================
elif "Modelo 3" in modelo_dashboard:
    st.markdown("#### 📊 Modelo 3: Matriz Térmica de Demanda Eléctrica")
    
    df_filtered['Hora'] = df_filtered['Timestamp'].dt.hour
    df_filtered['Dia_Semana'] = df_filtered['Timestamp'].dt.day_name()
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    df_heatmap = df_filtered.groupby(['Hora', 'Dia_Semana'])['Potencia_Activa_kW'].sum().unstack(fill_value=0)
    df_heatmap = df_heatmap.reindex(columns=[d for d in days_order if d in df_heatmap.columns])
    
    st.subheader(f"🗓️ Mapa de Calor de Demanda Eléctrica (kW) - {subestation_opt}")
    
    fig_heat = px.imshow(
        df_heatmap,
        labels=dict(x="Día de la Semana", y="Hora del Día", color="Demanda (kW)"),
        x=df_heatmap.columns,
        y=df_heatmap.index,
        color_continuous_scale='Viridis',
        template='plotly_dark'
    )
    fig_heat.update_layout(height=450, margin=dict(l=40, r=20, t=20, b=20))
    fig_heat.update_yaxes(tickmode='linear', tick0=0, dtick=1)
    st.plotly_chart(fig_heat, use_container_width=True)