"""Sales & revenue deep-dive: trends, seasonality, mix, discounts."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header("Sales & revenue", "Where revenue comes from and how it moves over time.")
    f = data.get_frames()
    li = f["line_items"]
    if li.empty:
        st.info("No data for the current filters.")
        return

    li = li.copy()
    li["month"] = li["order_date"].dt.to_period("M").dt.to_timestamp()
    li["year"] = li["order_date"].dt.year

    # ---- revenue by category over time (stacked) ----
    st.markdown("**Net revenue by category over time**")
    cat_month = li.groupby(["month", "category"])["net_amount"].sum().reset_index()
    fig = px.area(cat_month, x="month", y="net_amount", color="category")
    fig.update_layout(height=360, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Year-over-year net revenue**")
        yoy = li.groupby("year")["net_amount"].sum().reset_index()
        fig2 = px.bar(yoy, x="year", y="net_amount", text_auto=".2s")
        fig2.update_traces(marker_color=theme.ACCENT)
        fig2.update_layout(
            height=320, xaxis_title=None, yaxis_title=None, xaxis={"type": "category"}
        )
        st.plotly_chart(fig2, width="stretch")

    with c2:
        st.markdown("**Revenue mix by price band**")
        band = li.groupby("price_band")["net_amount"].sum().reset_index()
        order = ["budget", "mid", "premium", "luxury"]
        band["price_band"] = band["price_band"].astype("category")
        band = band.set_index("price_band").reindex(order).dropna().reset_index()
        fig3 = px.pie(band, values="net_amount", names="price_band", hole=0.55)
        fig3.update_layout(height=320)
        st.plotly_chart(fig3, width="stretch")

    # ---- seasonality: monthly index ----
    st.markdown("**Seasonality — average revenue by calendar month**")
    li["cal_month"] = li["order_date"].dt.month
    seas = li.groupby("cal_month")["net_amount"].sum().reset_index()
    seas["cal_month"] = seas["cal_month"].map(
        {
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        }
    )
    fig4 = px.bar(seas, x="cal_month", y="net_amount")
    fig4.update_traces(marker_color=theme.GOLD)
    fig4.update_layout(height=300, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig4, width="stretch")

    # ---- discount impact ----
    st.markdown("**Discount depth vs volume**")
    disc = li.assign(
        disc_pct=(li["discount_amount"] / li["gross_amount"].replace(0, 1) * 100).round(0)
    )
    dd = (
        disc.groupby("disc_pct")
        .agg(net=("net_amount", "sum"), lines=("order_item_id", "count"))
        .reset_index()
    )
    fig5 = px.scatter(
        dd, x="disc_pct", y="net", size="lines", color="net", color_continuous_scale="Teal"
    )
    fig5.update_layout(height=320, xaxis_title="discount %", yaxis_title="net revenue")
    st.plotly_chart(fig5, width="stretch")
