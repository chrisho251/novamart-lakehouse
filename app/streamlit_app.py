"""NovaMart analytics — multi-page dashboard entrypoint.

Uses st.navigation (Streamlit >= 1.36) to compose the pages under app/views/.
Global filters live in the sidebar and are applied by the shared data layer, so
every page stays in sync. Runs against Databricks SQL (gold star schema) when
credentials are present, and otherwise against the local CSV sample.

    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import datetime as dt

import streamlit as st
from lib import data, theme
from views import customers, operations, overview, payments, pipeline, sales

st.set_page_config(page_title="NovaMart Analytics", page_icon="🏬", layout="wide")
theme.install_template()


def sidebar_filters():
    """Populate st.session_state['filters'] from the unfiltered data."""
    try:
        li = data.load_raw()["line_items"]
    except FileNotFoundError as e:
        st.sidebar.error(str(e))
        st.session_state["filters"] = {}
        return

    with st.sidebar:
        st.markdown("## 🏬 NovaMart")
        st.caption(data.source_label())
        st.divider()
        st.subheader("Filters")

        dmin = li["order_date"].min().date()
        dmax = li["order_date"].max().date()
        default_start = max(dmin, dmax - dt.timedelta(days=365))
        date_range = st.date_input(
            "Date range", value=(default_start, dmax), min_value=dmin, max_value=dmax
        )
        regions = sorted(li["region"].dropna().unique())
        categories = sorted(li["category"].dropna().unique())
        segments = sorted(li["segment"].dropna().unique())

        sel_regions = st.multiselect("Region", regions, default=regions)
        sel_categories = st.multiselect("Category", categories, default=categories)
        sel_segments = st.multiselect("Segment", segments, default=segments)

        if st.button("Reset filters", width="stretch"):
            st.session_state.pop("filters", None)
            st.rerun()

    # normalize date_input (can return a single date mid-edit)
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        dr = (date_range[0], date_range[1])
    else:
        dr = (dmin, dmax)

    st.session_state["filters"] = {
        "date_range": dr,
        "regions": sel_regions,
        "categories": sel_categories,
        "segments": sel_segments,
    }


def main():
    sidebar_filters()

    nav = st.navigation(
        {
            "Business": [
                st.Page(
                    overview.render, title="Overview", icon="📊", url_path="overview", default=True
                ),
                st.Page(sales.render, title="Sales & revenue", icon="💰", url_path="sales"),
                st.Page(customers.render, title="Customers", icon="🧑‍🤝‍🧑", url_path="customers"),
            ],
            "Operations": [
                st.Page(operations.render, title="Operations", icon="📦", url_path="operations"),
                st.Page(payments.render, title="Payments", icon="💳", url_path="payments"),
            ],
            "Platform": [
                st.Page(pipeline.render, title="Pipeline health", icon="🩺", url_path="pipeline"),
            ],
        }
    )
    nav.run()


main()
