"""Executive overview: the headline numbers and trends."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header("Executive overview", "The headline health of the business at a glance.")
    f = data.get_frames()
    li, orders = f["line_items"], f["orders"]

    if li.empty:
        st.info("No data for the current filters.")
        return

    net = li["net_amount"].sum()
    margin = li["margin_amount"].sum()
    units = li["quantity"].sum()
    n_orders = orders["order_id"].nunique()
    aov = net / max(n_orders, 1)
    margin_pct = margin / net * 100 if net else 0

    theme.kpi_row(
        [
            ("Net revenue", theme.fmt_money(net), None),
            ("Orders", theme.fmt_int(n_orders), None),
            ("Units sold", theme.fmt_int(units), None),
            ("Avg order value", theme.fmt_money(aov), None),
            ("Gross margin", f"{margin_pct:.1f}%", None),
        ]
    )

    st.divider()

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**Net revenue over time**")
        trend = li.set_index("order_date").resample("MS")["net_amount"].sum().reset_index()
        fig = px.area(trend, x="order_date", y="net_amount")
        fig.update_traces(line_color=theme.ACCENT, fillcolor=theme.ACCENT_SOFT)
        fig.update_layout(height=320, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, width="stretch")

    with right:
        st.markdown("**Revenue by region**")
        by_region = li.groupby("region")["net_amount"].sum().sort_values().reset_index()
        fig2 = px.bar(by_region, x="net_amount", y="region", orientation="h")
        fig2.update_traces(marker_color=theme.GOLD)
        fig2.update_layout(height=320, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig2, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top categories by net revenue**")
        by_cat = (
            li.groupby("category")["net_amount"].sum().sort_values(ascending=False).reset_index()
        )
        fig3 = px.bar(by_cat, x="net_amount", y="category", orientation="h")
        fig3.update_traces(marker_color=theme.ACCENT)
        fig3.update_layout(
            height=360,
            yaxis={"categoryorder": "total ascending"},
            yaxis_title=None,
            xaxis_title=None,
        )
        st.plotly_chart(fig3, width="stretch")

    with c2:
        st.markdown("**Order lifecycle funnel**")
        funnel = data.status_funnel(orders)
        fig4 = px.funnel(funnel, x="orders", y="stage")
        fig4.update_traces(marker_color=theme.ACCENT)
        fig4.update_layout(height=360, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig4, width="stretch")
