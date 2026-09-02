import plotly.express as px
import plotly.graph_objects as go

from config import EFFICIENCY_TARGET_PCT

# Same locale fix as streamlit/charts.py: comma decimal / period thousands
# (Venezuelan convention), plain grouped integers instead of Plotly's default
# SI-prefix "12.973k" abbreviation.
NUMBER_LAYOUT = dict(separators=",.")
NUMBER_FMT = ",.0f"


def render_efficiency_gauge(value_pct: float, color: str, title: str) -> go.Figure:
    """Same semi-circle gauge idiom as streamlit/charts.py's per-machine
    gauges: a light-red zone below target, light-gray zone above it, red
    threshold line at the target value."""
    target = EFFICIENCY_TARGET_PCT
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(value_pct, 1),
        number={"suffix": "%", "font": {"size": 30}},
        title={"text": title, "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"size": 10}},
            "bar": {"color": color},
            "steps": [
                {"range": [0, target], "color": "#FFCCCC"},
                {"range": [target, 100], "color": "#E6E6E6"},
            ],
            "threshold": {"line": {"color": "red", "width": 3}, "thickness": 0.75, "value": target},
        },
    ))
    fig.update_layout(height=190, paper_bgcolor="white", margin=dict(t=45, b=10, l=25, r=25))
    return fig


def _compact_k(value: float) -> str:
    """'118k' style compact label for a bar's value text -- written out
    explicitly rather than left to Plotly's automatic SI-prefix formatting,
    since that auto-format is exactly what caused the earlier hover-text bug
    fixed in streamlit/charts.py. A literal string here can't drift."""
    return f"{value / 1000:,.0f}k".replace(",", ".")


def render_type_bar_chart(labels: list, values: list, colors: list) -> go.Figure:
    """Production subtotal per machine-type, in the caller's given order
    (the real production-flow order for that line). Bare bars -- no axis
    line, no gridlines, no tick numbers -- just the compact value above each
    bar and its type label below, matching the dashboard mockup."""
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[_compact_k(v) for v in values], textposition="outside",
        textfont=dict(size=13, color="#1f2937"),
        hovertemplate="%{x}: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", **NUMBER_LAYOUT,
        xaxis=dict(type="category", showgrid=False, showline=False, zeroline=False, tickfont=dict(size=12, color="#6b7280")),
        yaxis=dict(visible=False, range=[0, max(values) * 1.25 if values else 1]),
        height=190, margin=dict(t=30, b=25, l=15, r=15), showlegend=False,
        bargap=0.35,
    )
    return fig
