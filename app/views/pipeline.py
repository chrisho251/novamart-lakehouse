"""Pipeline health: volumes, freshness, and data-quality checks.

Mirrors the kind of observability a data platform team keeps on the gold layer —
useful signal that the pipeline is not just running but *correct*.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from lib import data, theme


def render():
    theme.page_header(
        "Pipeline health",
        "Volumes, freshness, and automated data-quality checks on the gold layer.",
    )
    f = data.get_frames()
    li, orders, payments = f["line_items"], f["orders"], f["payments"]
    st.caption(f"Source: {data.source_label()}")

    if li.empty:
        st.info("No data for the current filters.")
        return

    # ---- volumes ----
    st.markdown("**Row volumes by entity**")
    vols = pd.DataFrame(
        {
            "entity": ["order_items", "orders", "payments", "customers"],
            "rows": [
                len(li),
                orders["order_id"].nunique(),
                len(payments),
                orders["customer_id"].nunique(),
            ],
        }
    )
    fig = px.bar(vols, x="rows", y="entity", orientation="h", text_auto=".2s")
    fig.update_traces(marker_color=theme.ACCENT)
    fig.update_layout(height=240, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")

    fresh = li["order_date"].max()
    span = f"{li['order_date'].min():%Y-%m-%d} → {fresh:%Y-%m-%d}"
    theme.kpi_row(
        [
            ("Latest event", f"{fresh:%Y-%m-%d}", None),
            ("History span", span, None),
            ("Order items", theme.fmt_int(len(li)), None),
            ("Distinct orders", theme.fmt_int(orders["order_id"].nunique()), None),
        ]
    )

    st.divider()
    st.markdown("**Automated data-quality checks**")

    checks = _run_checks(li, orders, payments)
    cdf = pd.DataFrame(checks)
    passed = int((cdf["status"] == "PASS").sum())
    st.caption(f"{passed}/{len(cdf)} checks passing")

    def _style(row):
        color = "#1f7a1f" if row["status"] == "PASS" else theme.DANGER
        return [f"color: {color}; font-weight:600" if c == "status" else "" for c in row.index]

    st.dataframe(
        cdf.style.apply(_style, axis=1),
        width="stretch",
        hide_index=True,
    )

    st.markdown("**Daily ingested volume** (proxy for pipeline throughput)")
    daily = li.set_index("order_date").resample("D")["order_item_id"].count().reset_index()
    fig2 = px.bar(daily, x="order_date", y="order_item_id")
    fig2.update_traces(marker_color=theme.SILVER)
    fig2.update_layout(height=260, xaxis_title=None, yaxis_title="order items / day")
    st.plotly_chart(fig2, width="stretch")


def _run_checks(li, orders, payments) -> list[dict]:
    def chk(name, ok, detail):
        return {"check": name, "status": "PASS" if ok else "FAIL", "detail": detail}

    orphan_items = (~li["order_id"].isin(orders["order_id"])).sum()
    neg_net = (li["net_amount"] < 0).sum()
    null_cat = li["category"].isna().sum()
    orders_wo_pay = (~orders["order_id"].isin(payments["order_id"])).sum()
    bad_status = (
        ~orders["status"].isin(["placed", "paid", "shipped", "delivered", "canceled", "returned"])
    ).sum()
    dup_items = li["order_item_id"].duplicated().sum()

    return [
        chk("no orphan order_items", orphan_items == 0, f"{orphan_items} orphans"),
        chk("unique order_item_id", dup_items == 0, f"{dup_items} duplicates"),
        chk("net_amount >= 0", neg_net == 0, f"{neg_net} negative rows"),
        chk("category not null", null_cat == 0, f"{null_cat} nulls"),
        chk("every order has a payment", orders_wo_pay == 0, f"{orders_wo_pay} missing"),
        chk("order status in domain", bad_status == 0, f"{bad_status} invalid"),
    ]
