"""Pure, dependency-free record builders and business rules.

Everything here is deterministic given a ``random.Random`` instance, which makes
the money math and the order lifecycle unit-testable without a database, without
Faker, and without Spark.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------- #
# Reference data (small, closed vocabularies -> become gold dimensions)
# --------------------------------------------------------------------------- #

CUSTOMER_SEGMENTS = ("consumer", "small_business", "corporate")
SEGMENT_WEIGHTS = (0.72, 0.20, 0.08)

PRODUCT_CATEGORIES = (
    "electronics",
    "home_kitchen",
    "fashion",
    "beauty_health",
    "sports_outdoors",
    "toys_games",
    "books_media",
    "grocery",
    "automotive",
    "office_supplies",
)
# Rough per-category base price ranges (min, max) in the store currency.
CATEGORY_PRICE_RANGE = {
    "electronics": (25.0, 1800.0),
    "home_kitchen": (8.0, 600.0),
    "fashion": (10.0, 350.0),
    "beauty_health": (5.0, 200.0),
    "sports_outdoors": (12.0, 900.0),
    "toys_games": (6.0, 300.0),
    "books_media": (4.0, 90.0),
    "grocery": (2.0, 120.0),
    "automotive": (15.0, 1200.0),
    "office_supplies": (3.0, 400.0),
}

PAYMENT_METHODS = ("credit_card", "debit_card", "pix", "boleto", "wallet")
PAYMENT_WEIGHTS = (0.46, 0.18, 0.22, 0.08, 0.06)

FULFILLMENT_TYPES = ("marketplace", "fulfilled_by_novamart", "dropship")

# Order status lifecycle. Each order walks a prefix of the happy path and may
# branch to a terminal cancel/return state.
STATUS_PLACED = "placed"
STATUS_PAID = "paid"
STATUS_SHIPPED = "shipped"
STATUS_DELIVERED = "delivered"
STATUS_CANCELED = "canceled"
STATUS_RETURNED = "returned"

HAPPY_PATH = (STATUS_PLACED, STATUS_PAID, STATUS_SHIPPED, STATUS_DELIVERED)
ALL_STATUSES = HAPPY_PATH + (STATUS_CANCELED, STATUS_RETURNED)

# US-style regions -> states, so dim_geography has a real hierarchy.
REGION_STATES = {
    "west": ["CA", "WA", "OR", "NV", "AZ"],
    "south": ["TX", "FL", "GA", "NC", "TN"],
    "midwest": ["IL", "OH", "MI", "MN", "MO"],
    "northeast": ["NY", "MA", "PA", "NJ", "CT"],
}
ALL_STATES = [(s, region) for region, states in REGION_STATES.items() for s in states]


# --------------------------------------------------------------------------- #
# Records (kept as plain dicts so they serialize cheaply to CSV / COPY)
# --------------------------------------------------------------------------- #


def weighted_choice(rng: random.Random, choices: tuple, weights: tuple):
    """Deterministic weighted pick from ``choices`` given ``rng``."""
    return rng.choices(choices, weights=weights, k=1)[0]


def build_customer(cid: int, rng: random.Random, name: str, email: str, city: str) -> dict:
    state, region = rng.choice(ALL_STATES)
    created = _random_datetime(rng, date(2019, 1, 1), date(2024, 12, 31))
    return {
        "customer_id": cid,
        "full_name": name,
        "email": email,
        "segment": weighted_choice(rng, CUSTOMER_SEGMENTS, SEGMENT_WEIGHTS),
        "city": city,
        "state": state,
        "region": region,
        "created_at": created,
        "updated_at": created,
    }


def build_seller(sid: int, rng: random.Random, name: str, city: str) -> dict:
    state, region = rng.choice(ALL_STATES)
    return {
        "seller_id": sid,
        "seller_name": name,
        "city": city,
        "state": state,
        "region": region,
        "fulfillment_type": rng.choice(FULFILLMENT_TYPES),
        "rating": round(rng.uniform(3.2, 5.0), 2),
        "created_at": _random_datetime(rng, date(2018, 1, 1), date(2023, 12, 31)),
    }


def build_product(pid: int, rng: random.Random, name: str) -> dict:
    category = rng.choice(PRODUCT_CATEGORIES)
    lo, hi = CATEGORY_PRICE_RANGE[category]
    # Log-uniform gives a realistic long tail of prices.
    price = round(_log_uniform(rng, lo, hi), 2)
    cost = round(price * rng.uniform(0.45, 0.80), 2)
    created = _random_datetime(rng, date(2018, 6, 1), date(2024, 6, 30))
    return {
        "product_id": pid,
        "product_name": name,
        "category": category,
        "unit_price": price,
        "unit_cost": cost,
        "created_at": created,
        "updated_at": created,
    }


def order_line_net(quantity: int, unit_price: float, discount_pct: float) -> float:
    """Net revenue for a single order line. Additive by construction.

    >>> order_line_net(3, 10.0, 0.10)
    27.0
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if not 0.0 <= discount_pct < 1.0:
        raise ValueError("discount_pct must be in [0, 1)")
    return round(quantity * unit_price * (1.0 - discount_pct), 2)


def pick_status(rng: random.Random) -> str:
    """Pick a *current* order status with a realistic mix.

    Most orders reach a happy-path state; a minority are canceled or returned.
    """
    roll = rng.random()
    if roll < 0.02:
        return STATUS_CANCELED
    if roll < 0.05:
        return STATUS_RETURNED
    # Bias toward completed orders but keep a live tail of in-flight ones.
    return weighted_choice(
        rng,
        HAPPY_PATH,
        (0.05, 0.10, 0.15, 0.70),
    )


def status_history(
    current: str, order_ts: datetime, rng: random.Random
) -> list[tuple[str, datetime]]:
    """Return the ordered (status, timestamp) transitions leading to ``current``.

    A ``paid`` order has been ``placed`` then ``paid``; a ``returned`` order
    walked the whole happy path first. This is what the CDC mutator replays and
    what powers dim_order_status / fact freshness.
    """
    if current == STATUS_CANCELED:
        chain = [STATUS_PLACED, STATUS_CANCELED]
    elif current == STATUS_RETURNED:
        chain = list(HAPPY_PATH) + [STATUS_RETURNED]
    else:
        idx = HAPPY_PATH.index(current)
        chain = list(HAPPY_PATH[: idx + 1])

    out: list[tuple[str, datetime]] = []
    ts = order_ts
    for status in chain:
        out.append((status, ts))
        # each transition takes a few hours to a couple of days
        ts = ts + timedelta(hours=rng.uniform(1.0, 48.0))
    return out


def build_order(
    order_id: int, customer_id: int, seller_id: int, order_ts: datetime, rng: random.Random
) -> dict:
    current = pick_status(rng)
    history = status_history(current, order_ts, rng)
    updated_at = history[-1][1]
    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "seller_id": seller_id,
        "status": current,
        "order_ts": order_ts,
        "updated_at": updated_at,
        # convenience for the mutator: the full planned chain
        "_history": history,
    }


def build_order_items(
    order_id: int,
    product_ids_prices: list[tuple[int, float]],
    start_item_id: int,
    rng: random.Random,
) -> list[dict]:
    """Build 1..n line items for an order from a small product sample."""
    items = []
    for i, (product_id, list_price) in enumerate(product_ids_prices):
        quantity = rng.choices((1, 2, 3, 4, 5), weights=(0.55, 0.25, 0.1, 0.06, 0.04))[0]
        discount = rng.choices((0.0, 0.05, 0.10, 0.20), weights=(0.7, 0.15, 0.1, 0.05))[0]
        # sale price wiggles slightly around list price
        unit_price = round(list_price * rng.uniform(0.98, 1.02), 2)
        items.append(
            {
                "order_item_id": start_item_id + i,
                "order_id": order_id,
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_pct": discount,
                "net_amount": order_line_net(quantity, unit_price, discount),
            }
        )
    return items


def build_payment(payment_id: int, order: dict, order_total: float, rng: random.Random) -> dict:
    method = weighted_choice(rng, PAYMENT_METHODS, PAYMENT_WEIGHTS)
    installments = 1
    if method == "credit_card" and order_total > 100:
        installments = rng.choices((1, 3, 6, 12), weights=(0.6, 0.2, 0.12, 0.08))[0]
    paid = order["status"] not in (STATUS_PLACED, STATUS_CANCELED)
    return {
        "payment_id": payment_id,
        "order_id": order["order_id"],
        "payment_method": method,
        "installments": installments,
        "amount": order_total,
        "status": "captured" if paid else "pending",
        "paid_ts": order["updated_at"] if paid else None,
    }


# --------------------------------------------------------------------------- #
# Seasonality: orders per day are not flat.
# --------------------------------------------------------------------------- #


def seasonality_weight(d: date) -> float:
    """A multiplier on daily order volume: weekend dip, Q4/holiday surge."""
    w = 1.0
    # November/December surge (holiday shopping)
    if d.month in (11, 12):
        w *= 1.8
    elif d.month in (1,):  # January slump
        w *= 0.8
    # weekend lift for consumer retail
    if d.weekday() >= 5:
        w *= 1.15
    return w


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _random_datetime(rng: random.Random, start: date, end: date) -> datetime:
    delta_days = (end - start).days
    day = start + timedelta(days=rng.randint(0, max(delta_days, 0)))
    return datetime(
        day.year, day.month, day.day, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
    )


def _log_uniform(rng: random.Random, lo: float, hi: float) -> float:
    import math

    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


@dataclass
class ScaleConfig:
    """Row counts derived from a single scale factor."""

    scale: float = 1.0
    base_customers: int = 250_000
    base_sellers: int = 5_000
    base_products: int = 50_000
    base_orders: int = 2_000_000
    start_date: date = date(2022, 1, 1)
    end_date: date = date(2024, 12, 31)
    _counts: dict = field(default_factory=dict)

    @property
    def customers(self) -> int:
        return max(int(self.base_customers * self.scale), 10)

    @property
    def sellers(self) -> int:
        return max(int(self.base_sellers * self.scale), 3)

    @property
    def products(self) -> int:
        return max(int(self.base_products * self.scale), 20)

    @property
    def orders(self) -> int:
        return max(int(self.base_orders * self.scale), 20)
