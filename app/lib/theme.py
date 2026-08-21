"""Shared visual language for the dashboard — colors, plotly template, helpers."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Palette mirrors docs/architecture.html
ACCENT = "#0E8C86"
ACCENT_SOFT = "rgba(14,140,134,0.15)"
BRONZE = "#B0702F"
SILVER = "#6E7C8A"
GOLD = "#B5871B"
DANGER = "#C0492F"
MUTED = "#6E7C8A"

# Categorical palette for series (teal-anchored, colorblind-friendly-ish)
CATEGORICAL = [
    "#0E8C86",
    "#B5871B",
    "#B0702F",
    "#3E6E8E",
    "#6E7C8A",
    "#8A9A5B",
    "#C0492F",
    "#4C8C7D",
    "#9A6A9E",
    "#557A95",
]

# Status colors carry meaning across pages.
STATUS_COLORS = {
    "placed": "#8A9AA6",
    "paid": "#3E6E8E",
    "shipped": "#4C8C7D",
    "delivered": ACCENT,
    "canceled": "#C0492F",
    "returned": "#D08A3E",
}


def install_template():
    """Register + activate a shared plotly template so every chart matches."""
    tmpl = go.layout.Template()
    tmpl.layout = go.Layout(
        colorway=CATEGORICAL,
        font=dict(family="IBM Plex Sans, system-ui, sans-serif", size=13),
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    pio.templates["novamart"] = tmpl
    pio.templates.default = "plotly+novamart"


def fmt_money(x: float) -> str:
    ax = abs(x)
    if ax >= 1e9:
        return f"${x/1e9:.2f}B"
    if ax >= 1e6:
        return f"${x/1e6:.2f}M"
    if ax >= 1e3:
        return f"${x/1e3:.1f}K"
    return f"${x:,.0f}"


def fmt_int(x: float) -> str:
    ax = abs(x)
    if ax >= 1e6:
        return f"{x/1e6:.2f}M"
    if ax >= 1e3:
        return f"{x/1e3:.1f}K"
    return f"{x:,.0f}"


def kpi_row(items: list[tuple[str, str, str | None]]):
    """Render a row of metrics. Each item = (label, value, delta_or_None)."""
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items, strict=False):
        col.metric(label, value, delta)


def page_header(title: str, subtitle: str):
    st.markdown(f"### {title}")
    st.caption(subtitle)
