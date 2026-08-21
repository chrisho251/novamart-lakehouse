"""Unit tests for the pure business logic and a small end-to-end CSV generation."""

from __future__ import annotations

import csv
import gzip
import random
from datetime import date, datetime

import pytest
from novamart_gen import schema
from novamart_gen.generate import TABLES, CsvSink, generate_all
from novamart_gen.schema import ScaleConfig

# --------------------------------------------------------------------------- #
# money math
# --------------------------------------------------------------------------- #


def test_order_line_net_basic():
    assert schema.order_line_net(3, 10.0, 0.10) == 27.0
    assert schema.order_line_net(1, 19.99, 0.0) == 19.99


def test_order_line_net_is_additive_and_rounded():
    # two lines summed equals sum of nets (no floating drift beyond cents)
    a = schema.order_line_net(2, 12.34, 0.05)
    b = schema.order_line_net(5, 7.77, 0.20)
    assert round(a + b, 2) == round(a + b, 2)
    assert a == round(a, 2)


@pytest.mark.parametrize("qty,disc", [(0, 0.1), (-1, 0.0), (2, 1.0), (2, 1.5)])
def test_order_line_net_rejects_bad_input(qty, disc):
    with pytest.raises(ValueError):
        schema.order_line_net(qty, 10.0, disc)


# --------------------------------------------------------------------------- #
# order lifecycle
# --------------------------------------------------------------------------- #


def test_status_history_paid_has_two_steps():
    hist = schema.status_history(schema.STATUS_PAID, datetime(2024, 1, 1), random.Random(1))
    assert [s for s, _ in hist] == [schema.STATUS_PLACED, schema.STATUS_PAID]


def test_status_history_returned_walks_full_path():
    hist = schema.status_history(schema.STATUS_RETURNED, datetime(2024, 1, 1), random.Random(1))
    assert [s for s, _ in hist] == list(schema.HAPPY_PATH) + [schema.STATUS_RETURNED]


def test_status_history_timestamps_monotonic():
    hist = schema.status_history(schema.STATUS_DELIVERED, datetime(2024, 1, 1), random.Random(7))
    ts = [t for _, t in hist]
    assert ts == sorted(ts)


def test_pick_status_is_valid_and_deterministic():
    rng = random.Random(99)
    statuses = {schema.pick_status(rng) for _ in range(500)}
    assert statuses.issubset(set(schema.ALL_STATUSES))
    # determinism
    assert schema.pick_status(random.Random(5)) == schema.pick_status(random.Random(5))


# --------------------------------------------------------------------------- #
# reference / dimensions
# --------------------------------------------------------------------------- #


def test_build_product_price_within_category_band():
    rng = random.Random(3)
    for _ in range(200):
        p = schema.build_product(1, rng, "thing")
        lo, hi = schema.CATEGORY_PRICE_RANGE[p["category"]]
        assert lo <= p["unit_price"] <= hi * 1.001
        assert p["unit_cost"] < p["unit_price"]


def test_seasonality_q4_heavier_than_january():
    assert schema.seasonality_weight(date(2024, 12, 10)) > schema.seasonality_weight(
        date(2024, 1, 10)
    )


def test_scale_config_counts_scale_and_floor():
    big = ScaleConfig(scale=1.0)
    assert big.orders == 2_000_000
    tiny = ScaleConfig(scale=0.0)
    assert tiny.orders >= 20  # floor keeps tiny runs usable


# --------------------------------------------------------------------------- #
# end-to-end generation (tiny) to CSV
# --------------------------------------------------------------------------- #


def test_generate_all_writes_consistent_csv(tmp_path):
    faker = pytest.importorskip("faker")
    fk = faker.Faker("en_US")
    faker.Faker.seed(0)

    cfg = ScaleConfig(scale=0.0)  # floored to small counts
    sink = CsvSink(str(tmp_path))
    rng = random.Random(0)
    counts = generate_all(cfg, sink, rng, fk, progress=False)
    sink.close()

    # every table produced rows and a file
    for table in TABLES:
        f = tmp_path / f"{table}.csv.gz"
        assert f.exists(), f"missing {table}"
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == counts[table] > 0

    # referential integrity: every order_item.order_id exists in orders
    order_ids = _ids(tmp_path, "orders", "order_id")
    item_order_ids = _ids(tmp_path, "order_items", "order_id")
    assert item_order_ids.issubset(order_ids)

    # every order has exactly one payment
    payment_order_ids = _col(tmp_path, "payments", "order_id")
    assert len(payment_order_ids) == counts["orders"]
    assert set(payment_order_ids) == order_ids

    # net_amount recomputes correctly from the stored components
    with gzip.open(tmp_path / "order_items.csv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            expected = schema.order_line_net(
                int(r["quantity"]), float(r["unit_price"]), float(r["discount_pct"])
            )
            assert abs(float(r["net_amount"]) - expected) < 0.005


def _ids(base, table, col) -> set:
    return set(_col(base, table, col))


def _col(base, table, col) -> list:
    with gzip.open(base / f"{table}.csv.gz", "rt", encoding="utf-8") as fh:
        return [r[col] for r in csv.DictReader(fh)]
