"""Operations: order lifecycle, cancellations/returns, fulfillment, sellers."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header(
        "Operations & fulfillment", "How orders flow, where they fall out, and who fulfills them."
    )
    f = data.get_frames()
    orders, li = f["orders"], f["line_items"]
    if orders.empty:
        st.info("No data for the current filters.")
        return

    rates = data.reversal_rates(orders)
    funnel = data.status_funnel(orders)
    delivered = int(funnel.loc[funnel["stage"] == "delivered", "orders"].iloc[0])
    total = len(orders)

    theme.kpi_row(
        [
            ("Total orders", theme.fmt_int(total), None),
            ("Delivered", f"{delivered/max(total,1)*100:.1f}%", None),
            ("Cancel rate", f"{rates['cancel_rate']:.1f}%", None),
            ("Return rate", f"{rates['return_rate']:.1f}%", None),
        ]
    )
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Order status funnel**")
        fig = px.funnel(funnel, x="orders", y="stage")
        fig.update_traces(marker_color=theme.ACCENT)
        fig.update_layout(height=340, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.markdown("**Current status mix**")
        mix = orders["status"].value_counts().reset_index()
        mix.columns = ["status", "orders"]
        fig2 = px.bar(
            mix,
            x="orders",
            y="status",
            orientation="h",
            color="status",
            color_discrete_map=theme.STATUS_COLORS,
        )
        fig2.update_layout(height=340, showlegend=False, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig2, width="stretch")

    st.markdown("**Fulfillment type — volume & revenue**")
    ful = (
        orders.groupby("fulfillment_type")
        .agg(orders=("order_id", "nunique"), revenue=("order_total", "sum"))
        .reset_index()
    )
    c3, c4 = st.columns(2)
    with c3:
        fig3 = px.bar(ful, x="fulfillment_type", y="orders")
        fig3.update_traces(marker_color=theme.SILVER)
        fig3.update_layout(height=300, xaxis_title=None, yaxis_title="orders")
        st.plotly_chart(fig3, width="stretch")
    with c4:
        fig4 = px.bar(ful, x="fulfillment_type", y="revenue")
        fig4.update_traces(marker_color=theme.GOLD)
        fig4.update_layout(height=300, xaxis_title=None, yaxis_title="net revenue")
        st.plotly_chart(fig4, width="stretch")

    # ---- top sellers ----
    st.markdown("**Top sellers by net revenue**")
    sellers = (
        li.groupby("seller_name")
        .agg(
            revenue=("net_amount", "sum"),
            orders=("order_id", "nunique"),
            items=("order_item_id", "count"),
        )
        .sort_values("revenue", ascending=False)
        .head(15)
        .reset_index()
    )
    sellers["revenue"] = sellers["revenue"].round(0)
    st.dataframe(sellers, width="stretch", hide_index=True)
