"""Data layer for the dashboard.

Loads a normalized set of frames — ``line_items``, ``orders``, ``payments``,
``customers`` — from Databricks SQL (gold star schema) when credentials are
present, and otherwise from the locally generated CSV sample so every page is
demoable offline. Pages consume the same column contract regardless of source.
"""

from __future__ import annotations

import glob
import gzip
import os

import pandas as pd
import streamlit as st

SAMPLE_DIR = os.environ.get("SAMPLE_DIR", "data/sample")

# Column contract every page relies on -------------------------------------- #
# line_items: order_id, order_item_id, order_date, category, price_band, region,
#   state, segment, seller_name, fulfillment_type, payment_method, status,
#   quantity, gross_amount, discount_amount, net_amount, cost_amount,
#   margin_amount, customer_id


def has_databricks() -> bool:
    return bool(os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"))


def _price_band(p: float) -> str:
    if p < 25:
        return "budget"
    if p < 150:
        return "mid"
    if p < 600:
        return "premium"
    return "luxury"


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


@st.cache_data(ttl=300, show_spinner="Loading data…")
def load_raw() -> dict:
    if has_databricks():
        try:
            return _from_databricks()
        except Exception as e:  # pragma: no cover - network dependent
            st.warning(f"Databricks connection failed — using local sample. ({e})")
    return _from_sample()


def source_label() -> str:
    return (
        "Databricks SQL · gold star schema"
        if has_databricks()
        else "Local CSV sample (offline demo)"
    )


def _read_csv_gz(name: str) -> pd.DataFrame:
    path = os.path.join(SAMPLE_DIR, f"{name}.csv.gz")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return pd.read_csv(fh)


def _from_sample() -> dict:
    if not glob.glob(os.path.join(SAMPLE_DIR, "*.csv.gz")):
        raise FileNotFoundError(
            f"No sample in {SAMPLE_DIR}. Run: "
            "python -m novamart_gen.generate --sink csv --scale 0.01 --out data/sample"
        )
    orders = _read_csv_gz("orders")
    items = _read_csv_gz("order_items")
    products = _read_csv_gz("products")[["product_id", "category", "unit_cost"]]
    customers = _read_csv_gz("customers")[["customer_id", "segment", "region", "state"]]
    sellers = _read_csv_gz("sellers")[["seller_id", "seller_name", "fulfillment_type"]]
    payments = _read_csv_gz("payments")

    orders["order_date"] = pd.to_datetime(orders["order_ts"])

    li = (
        items.merge(
            orders[["order_id", "customer_id", "seller_id", "status", "order_date"]], on="order_id"
        )
        .merge(products, on="product_id")
        .merge(customers, on="customer_id")
        .merge(sellers, on="seller_id")
        .merge(payments[["order_id", "payment_method"]], on="order_id", how="left")
    )
    li["gross_amount"] = li["quantity"] * li["unit_price"]
    li["discount_amount"] = li["gross_amount"] * li["discount_pct"]
    li["cost_amount"] = li["quantity"] * li["unit_cost"]
    li["margin_amount"] = li["net_amount"] - li["cost_amount"]
    li["price_band"] = li["unit_price"].apply(_price_band)

    line_items = li[
        [
            "order_id",
            "order_item_id",
            "order_date",
            "category",
            "price_band",
            "region",
            "state",
            "segment",
            "seller_name",
            "fulfillment_type",
            "payment_method",
            "status",
            "quantity",
            "gross_amount",
            "discount_amount",
            "net_amount",
            "cost_amount",
            "margin_amount",
            "customer_id",
        ]
    ].copy()

    pay = payments.copy()
    order_dates = orders.set_index("order_id")["order_date"]
    pay["order_date"] = pd.to_datetime(pay["paid_ts"])
    # fall back to the order timestamp for not-yet-captured (pending) payments
    pay["order_date"] = pay["order_date"].fillna(pay["order_id"].map(order_dates))
    payments_out = pay[
        [
            "payment_id",
            "order_id",
            "order_date",
            "payment_method",
            "installments",
            "amount",
            "status",
        ]
    ].rename(columns={"status": "payment_status"})

    return {
        "line_items": line_items,
        "payments": payments_out,
    }


def _from_databricks() -> dict:  # pragma: no cover - network dependent
    from databricks import sql

    cat = os.environ.get("DATABRICKS_CATALOG", "novamart")
    conn = sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].replace("https://", ""),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    line_items_q = f"""
        select
            f.order_id, f.order_item_id, f.order_ts as order_date,
            p.category, p.price_band, g.region, g.state, c.segment,
            s.seller_name, s.fulfillment_type, pm.payment_method, f.order_status as status,
            f.quantity, f.gross_amount, f.discount_amount, f.net_amount,
            f.cost_amount, f.margin_amount, c.customer_id
        from {cat}.gold.fct_order_items f
        left join {cat}.gold.dim_product p on f.product_key = p.product_key
        left join {cat}.gold.dim_geography g on f.geography_key = g.geography_key
        left join {cat}.gold.dim_customer c on f.customer_key = c.customer_key
        left join {cat}.gold.dim_seller s on f.seller_key = s.seller_key
        left join {cat}.gold.dim_payment_method pm on f.payment_method_key = pm.payment_method_key
    """
    payments_q = f"""
        select
            p.payment_id, p.order_id, p.event_ts as order_date, pm.payment_method,
            p.installments, p.payment_amount as amount, p.payment_status
        from {cat}.gold.fct_payments p
        left join {cat}.gold.dim_payment_method pm on p.payment_method_key = pm.payment_method_key
    """
    with conn:
        line_items = pd.read_sql(line_items_q, conn)
        payments = pd.read_sql(payments_q, conn)
    line_items["order_date"] = pd.to_datetime(line_items["order_date"])
    payments["order_date"] = pd.to_datetime(payments["order_date"])
    return {"line_items": line_items, "payments": payments}


# --------------------------------------------------------------------------- #
# Derived frames + filtering
# --------------------------------------------------------------------------- #


def derive_orders(line_items: pd.DataFrame) -> pd.DataFrame:
    return (
        line_items.groupby("order_id")
        .agg(
            customer_id=("customer_id", "first"),
            order_date=("order_date", "first"),
            status=("status", "first"),
            region=("region", "first"),
            segment=("segment", "first"),
            seller_name=("seller_name", "first"),
            fulfillment_type=("fulfillment_type", "first"),
            payment_method=("payment_method", "first"),
            order_total=("net_amount", "sum"),
            items=("order_item_id", "count"),
        )
        .reset_index()
    )


def derive_customers(orders: pd.DataFrame) -> pd.DataFrame:
    return (
        orders.groupby("customer_id")
        .agg(
            segment=("segment", "first"),
            region=("region", "first"),
            first_order_date=("order_date", "min"),
            last_order_date=("order_date", "max"),
            orders_count=("order_id", "nunique"),
            ltv=("order_total", "sum"),
        )
        .reset_index()
    )


def apply_filters(line_items: pd.DataFrame) -> pd.DataFrame:
    """Apply the global sidebar filters stored in session_state."""
    df = line_items
    f = st.session_state.get("filters", {})
    if f.get("date_range"):
        lo, hi = f["date_range"]
        df = df[(df["order_date"].dt.date >= lo) & (df["order_date"].dt.date <= hi)]
    if f.get("regions"):
        df = df[df["region"].isin(f["regions"])]
    if f.get("categories"):
        df = df[df["category"].isin(f["categories"])]
    if f.get("segments"):
        df = df[df["segment"].isin(f["segments"])]
    return df


def get_frames() -> dict:
    """Return filtered line_items + derived orders/customers/payments."""
    raw = load_raw()
    li = apply_filters(raw["line_items"])
    orders = derive_orders(li)
    customers = derive_customers(orders)
    pay = raw["payments"]
    pay = pay[pay["order_id"].isin(orders["order_id"])]
    return {"line_items": li, "orders": orders, "customers": customers, "payments": pay}


# --------------------------------------------------------------------------- #
# Analytics helpers shared by pages
# --------------------------------------------------------------------------- #

# Lifecycle: which current statuses imply a given stage was reached.
_REACHED = {
    "placed": {"placed", "paid", "shipped", "delivered", "returned", "canceled"},
    "paid": {"paid", "shipped", "delivered", "returned"},
    "shipped": {"shipped", "delivered", "returned"},
    "delivered": {"delivered", "returned"},
}


def status_funnel(orders: pd.DataFrame) -> pd.DataFrame:
    total = len(orders)
    rows = []
    for stage, reached in _REACHED.items():
        n = int(orders["status"].isin(reached).sum())
        rows.append({"stage": stage, "orders": n, "pct": (n / total * 100) if total else 0})
    return pd.DataFrame(rows)


def reversal_rates(orders: pd.DataFrame) -> dict:
    total = max(len(orders), 1)
    return {
        "cancel_rate": (orders["status"] == "canceled").sum() / total * 100,
        "return_rate": (orders["status"] == "returned").sum() / total * 100,
    }


def cohort_retention(orders: pd.DataFrame, max_offsets: int = 12) -> pd.DataFrame:
    """Monthly cohort retention matrix (rows=cohort month, cols=month offset)."""
    o = orders.copy()
    o["order_month"] = o["order_date"].dt.to_period("M")
    first = o.groupby("customer_id")["order_month"].min().rename("cohort")
    o = o.join(first, on="customer_id")
    o["offset"] = (o["order_month"] - o["cohort"]).apply(lambda x: x.n)
    o = o[(o["offset"] >= 0) & (o["offset"] < max_offsets)]

    cohort_sizes = o[o["offset"] == 0].groupby("cohort")["customer_id"].nunique()
    active = o.groupby(["cohort", "offset"])["customer_id"].nunique().reset_index()
    pivot = active.pivot(index="cohort", columns="offset", values="customer_id")
    retention = pivot.div(cohort_sizes, axis=0) * 100
    retention.index = retention.index.astype(str)
    return retention
