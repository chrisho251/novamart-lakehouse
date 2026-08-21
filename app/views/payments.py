"""Payments: method mix, installments, capture status."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header("Payments", "How customers pay and how reliably cash is captured.")
    f = data.get_frames()
    pay = f["payments"]
    if pay.empty:
        st.info("No data for the current filters.")
        return

    captured = pay[pay["payment_status"] == "captured"]["amount"].sum()
    total = pay["amount"].sum()
    capture_rate = captured / total * 100 if total else 0
    avg_installments = pay["installments"].mean()

    theme.kpi_row(
        [
            ("Payments", theme.fmt_int(len(pay)), None),
            ("Captured value", theme.fmt_money(captured), None),
            ("Capture rate", f"{capture_rate:.1f}%", None),
            ("Avg installments", f"{avg_installments:.2f}", None),
        ]
    )
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Payment method share (by value)**")
        by_method = pay.groupby("payment_method")["amount"].sum().reset_index()
        fig = px.pie(by_method, values="amount", names="payment_method", hole=0.55)
        fig.update_layout(height=340)
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.markdown("**Captured vs pending by method**")
        cs = pay.groupby(["payment_method", "payment_status"])["amount"].sum().reset_index()
        fig2 = px.bar(
            cs,
            x="payment_method",
            y="amount",
            color="payment_status",
            color_discrete_map={"captured": theme.ACCENT, "pending": theme.DANGER},
        )
        fig2.update_layout(height=340, barmode="stack", xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig2, width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Installment distribution**")
        inst = pay["installments"].value_counts().sort_index().reset_index()
        inst.columns = ["installments", "payments"]
        fig3 = px.bar(inst, x="installments", y="payments")
        fig3.update_traces(marker_color=theme.SILVER)
        fig3.update_layout(height=300, xaxis={"type": "category"}, yaxis_title=None)
        st.plotly_chart(fig3, width="stretch")

    with c4:
        st.markdown("**Payment value over time by method**")
        p = pay.copy()
        p["month"] = p["order_date"].dt.to_period("M").dt.to_timestamp()
        pm = p.groupby(["month", "payment_method"])["amount"].sum().reset_index()
        fig4 = px.area(pm, x="month", y="amount", color="payment_method")
        fig4.update_layout(height=300, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig4, width="stretch")
