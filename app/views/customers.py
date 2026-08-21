"""Customers & cohorts: segments, retention, LTV, new vs returning."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header(
        "Customers & cohorts", "Who buys, whether they come back, and what they're worth."
    )
    f = data.get_frames()
    orders, customers = f["orders"], f["customers"]
    if orders.empty:
        st.info("No data for the current filters.")
        return

    n_customers = customers["customer_id"].nunique()
    repeat = (customers["orders_count"] > 1).sum()
    repeat_rate = repeat / max(n_customers, 1) * 100
    avg_ltv = customers["ltv"].mean()

    theme.kpi_row(
        [
            ("Customers", theme.fmt_int(n_customers), None),
            ("Repeat customers", theme.fmt_int(repeat), None),
            ("Repeat rate", f"{repeat_rate:.1f}%", None),
            ("Avg lifetime value", theme.fmt_money(avg_ltv), None),
        ]
    )
    st.divider()

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("**Revenue by customer segment**")
        seg = orders.groupby("segment")["order_total"].sum().reset_index()
        fig = px.pie(seg, values="order_total", names="segment", hole=0.55)
        fig.update_layout(height=320)
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.markdown("**New vs returning orders over time**")
        o = orders.copy().sort_values("order_date")
        o["month"] = o["order_date"].dt.to_period("M").dt.to_timestamp()
        first = o.groupby("customer_id")["order_date"].transform("min")
        o["kind"] = (o["order_date"] > first).map({True: "returning", False: "new"})
        nr = o.groupby(["month", "kind"])["order_id"].nunique().reset_index()
        fig2 = px.bar(
            nr,
            x="month",
            y="order_id",
            color="kind",
            color_discrete_map={"new": theme.ACCENT, "returning": theme.GOLD},
        )
        fig2.update_layout(height=320, barmode="stack", xaxis_title=None, yaxis_title="orders")
        st.plotly_chart(fig2, width="stretch")

    # ---- cohort retention heatmap ----
    st.markdown("**Monthly cohort retention** (% of each cohort ordering again, by month offset)")
    ret = data.cohort_retention(orders)
    if ret.empty or ret.shape[1] <= 1:
        st.caption("Not enough history in the current filter to build cohorts.")
    else:
        fig3 = px.imshow(
            ret,
            aspect="auto",
            color_continuous_scale="Teal",
            labels=dict(x="months since first order", y="cohort", color="retention %"),
            text_auto=".0f",
        )
        fig3.update_layout(height=420)
        st.plotly_chart(fig3, width="stretch")

    # ---- LTV distribution ----
    st.markdown("**Lifetime value distribution**")
    fig4 = px.histogram(customers, x="ltv", nbins=40)
    fig4.update_traces(marker_color=theme.ACCENT)
    fig4.update_layout(height=300, xaxis_title="customer LTV", yaxis_title="customers")
    st.plotly_chart(fig4, width="stretch")
