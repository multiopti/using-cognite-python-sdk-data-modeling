import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

def get_avg_efficiency(df: pd.DataFrame) -> float:
    eff_series = df['% Eficiencia'].astype(str).str.replace('%', '').str.strip()
    eff_numeric = pd.to_numeric(eff_series, errors='coerce').fillna(0.0)
    non_zero = eff_numeric[eff_numeric > 0]
    return float(non_zero.mean()) if not non_zero.empty else 0.0

def render_machine_charts(filtered_df: pd.DataFrame, active_m_type: str, active_machine_label: str, active_turno: str):
    chart_col1, chart_col2 = st.columns(2)

    if active_m_type == "PRINTER":
        with chart_col1:
            fig_prod_line = px.line(
                filtered_df, x='Hora', y='Producción x hora', markers=True,
                labels={'Producción x hora': 'Unidades', 'Hora': 'Hora'},
                title=f"Producción por Hora: {active_machine_label} ({active_turno})"
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
                filtered_df, x='Hora', y='Retrac-x-hora',
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
                filtered_df, x='Hora', y='Golpes Bobina', markers=True,
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
                filtered_df, x='Hora', y='Tiempo Parada (min)',
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
                filtered_df, x='Hora', y='Producción x hora', markers=True,
                labels={'Producción x hora': 'Latas', 'Hora': 'Hora'},
                title=f"Latas x hora: {active_machine_label} ({active_turno})"
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
                filtered_df, x='Hora', y='Tiempo Parada (min)',
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
                filtered_df, x='Hora', y='PROD. LATAS', markers=True,
                labels={'PROD. LATAS': 'Latas Producidas', 'Hora': 'Hora'},
                title=f"Producción por Hora: {active_machine_label} ({active_turno})"
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

def render_gauges(filtered_df: pd.DataFrame, active_m_type: str):
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 5px;' />", unsafe_allow_html=True)
    gauge_col1, gauge_col2, gauge_col3, gauge_col4 = st.columns(4)

    if active_m_type == "PRINTER":
        total_prod = int(filtered_df['Producción x hora'].sum())
        total_retrac = int(filtered_df['Retrac-x-hora'].sum())
        total_blow = int(filtered_df['Blow of'].sum())
        total_downtime = round(filtered_df['Tiempo de parada'].sum(), 1)

        with gauge_col1:
            fig_prod = go.Figure(go.Indicator(
                mode="gauge+number", value=total_prod,
                title={'text': "Producción Total (Turno)", 'font': {'size': 13}},
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
                gauge={'axis': {'range': [0, 60000], 'tickfont': {'size': 10}},
                       'bar': {'color': "#0284c7"},
                       'steps': [{'range': [0, 36000], 'color': "#FFCCCC"}, {'range': [36000, 60000], 'color': "#E6E6E6"}]}
            ))
            fig_gb.update_layout(height=200, paper_bgcolor='white', margin=dict(t=50, b=10, l=25, r=25))
            st.plotly_chart(fig_gb, use_container_width=True)

        with gauge_col2:
            fig_gt = go.Figure(go.Indicator(
                mode="gauge+number", value=total_golpes_turno,
                title={'text': "Total Golpes Turno", 'font': {'size': 13}},
                gauge={'axis': {'range': [0, 60000], 'tickfont': {'size': 10}},
                       'bar': {'color': "#38bdf8"},
                       'steps': [{'range': [0, 36000], 'color': "#FFCCCC"}, {'range': [36000, 60000], 'color': "#E6E6E6"}]}
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
        total_cans_ispray = int(filtered_df['Producción x hora'].sum())
        avg_eff_ispray = get_avg_efficiency(filtered_df)
        total_downtime_ispray = round(filtered_df['Tiempo Parada (min)'].sum(), 1)

        with gauge_col1:
            fig_ispray_prod = go.Figure(go.Indicator(
                mode="gauge+number", value=total_cans_ispray,
                title={'text': "Total Latas", 'font': {'size': 13}},
                gauge={'axis': {'range': [0, 192000], 'tickfont': {'size': 10}},
                       'bar': {'color': "#10b981"},
                       'steps': [{'range': [0, 96000], 'color': "#FFCCCC"}, {'range': [96000, 192000], 'color': "#E6E6E6"}]}
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
            active_hours_count = int((filtered_df['Producción x hora'] > 0).sum())
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
                title={'text': "Producción Total (Latas)", 'font': {'size': 13}},
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