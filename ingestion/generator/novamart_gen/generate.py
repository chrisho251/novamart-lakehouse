"""Generate the NovaMart OLTP history and load it to a sink (CSV or Postgres).

Examples
--------
Small local run into CSV (no database required)::

    python -m novamart_gen.generate --sink csv --scale 0.01 --out ./data

Full 5M+ run straight into Postgres via COPY::

    python -m novamart_gen.generate --sink postgres --scale 1.0 \
        --dsn postgresql://nova:nova@localhost:5432/novamart

Continuously mutate order statuses to emit CDC change events::

    python -m novamart_gen.generate mutate --dsn ... --rate 50 --seconds 600
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import schema
from .schema import ScaleConfig

SEED = 42

TABLES = {
    "customers": [
        "customer_id",
        "full_name",
        "email",
        "segment",
        "city",
        "state",
        "region",
        "created_at",
        "updated_at",
    ],
    "sellers": [
        "seller_id",
        "seller_name",
        "city",
        "state",
        "region",
        "fulfillment_type",
        "rating",
        "created_at",
    ],
    "products": [
        "product_id",
        "product_name",
        "category",
        "unit_price",
        "unit_cost",
        "created_at",
        "updated_at",
    ],
    "orders": ["order_id", "customer_id", "seller_id", "status", "order_ts", "updated_at"],
    "order_items": [
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount_pct",
        "net_amount",
    ],
    "payments": [
        "payment_id",
        "order_id",
        "payment_method",
        "installments",
        "amount",
        "status",
        "paid_ts",
    ],
}


# --------------------------------------------------------------------------- #
# Sinks
# --------------------------------------------------------------------------- #


class CsvSink:
    """Writes one gzip-compressed CSV per table (also the batch-landing format)."""

    def __init__(self, out_dir: str):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, tuple] = {}

    def _writer(self, table: str):
        if table not in self._files:
            fh = gzip.open(self.out / f"{table}.csv.gz", "wt", newline="", encoding="utf-8")
            w = csv.writer(fh)
            w.writerow(TABLES[table])
            self._files[table] = (fh, w)
        return self._files[table][1]

    def write_row(self, table: str, row: dict):
        self._writer(table).writerow([row.get(c) for c in TABLES[table]])

    def close(self):
        for fh, _ in self._files.values():
            fh.close()


class PostgresSink:
    """Bulk-loads via COPY. Requires the ``postgres`` extra (psycopg 3)."""

    def __init__(self, dsn: str, batch: int = 50_000):
        try:
            import psycopg  # noqa: F401
        except ImportError as e:  # pragma: no cover - env dependent
            raise SystemExit("psycopg not installed. Run: pip install '.[postgres]'") from e
        import psycopg

        self.conn = psycopg.connect(dsn, autocommit=False)
        self.batch = batch
        self._buffers: dict[str, list] = {t: [] for t in TABLES}
        self._copy_ctx: dict[str, object] = {}

    def write_row(self, table: str, row: dict):
        buf = self._buffers[table]
        buf.append(tuple(row.get(c) for c in TABLES[table]))
        if len(buf) >= self.batch:
            self._flush(table)

    def _flush(self, table: str):
        buf = self._buffers[table]
        if not buf:
            return
        cols = ", ".join(TABLES[table])
        with self.conn.cursor() as cur:
            with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:
                for rec in buf:
                    copy.write_row(rec)
        self.conn.commit()
        buf.clear()

    def close(self):
        for t in TABLES:
            self._flush(t)
        self.conn.close()


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


def _faker():
    try:
        from faker import Faker
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Faker not installed. Run: pip install '.[dev]' or pip install Faker"
        ) from e
    fk = Faker("en_US")
    Faker.seed(SEED)
    return fk


def _day_picker(cfg: ScaleConfig):
    """Return (days, cumulative_weights) for seasonality-weighted day sampling."""
    days = []
    weights = []
    d = cfg.start_date
    total = 0.0
    while d <= cfg.end_date:
        days.append(d)
        total += schema.seasonality_weight(d)
        weights.append(total)
        d = d + timedelta(days=1)
    return days, weights, total


def generate_all(cfg: ScaleConfig, sink, rng: random.Random, fk, progress=True) -> dict:
    """Generate every table into ``sink``. Returns row counts."""
    counts = {t: 0 for t in TABLES}

    # ---- dimensions (kept slim in memory for referencing) ----
    customer_ids: list[int] = []
    for cid in range(1, cfg.customers + 1):
        row = schema.build_customer(cid, rng, fk.name(), fk.unique.email(), fk.city())
        sink.write_row("customers", row)
        customer_ids.append(cid)
    counts["customers"] = len(customer_ids)

    seller_ids: list[int] = []
    for sid in range(1, cfg.sellers + 1):
        sink.write_row("sellers", schema.build_seller(sid, rng, fk.company(), fk.city()))
        seller_ids.append(sid)
    counts["sellers"] = len(seller_ids)

    products: list[tuple[int, float]] = []  # (id, price) for referencing
    for pid in range(1, cfg.products + 1):
        row = schema.build_product(pid, rng, fk.catch_phrase()[:60])
        sink.write_row("products", row)
        products.append((pid, row["unit_price"]))
    counts["products"] = len(products)

    # ---- facts ----
    days, cum_weights, total_w = _day_picker(cfg)
    item_id = 1
    payment_id = 1
    n_orders = cfg.orders

    for order_id in range(1, n_orders + 1):
        # seasonality-weighted day
        r = rng.random() * total_w
        day = days[bisect.bisect_left(cum_weights, r)]
        order_ts = datetime(
            day.year, day.month, day.day, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
        )

        customer_id = rng.choice(customer_ids)
        seller_id = rng.choice(seller_ids)
        order = schema.build_order(order_id, customer_id, seller_id, order_ts, rng)
        sink.write_row("orders", order)
        counts["orders"] += 1

        # 1..6 distinct products, averaging ~2.7 items/order
        k = rng.choices((1, 2, 3, 4, 5, 6), weights=(0.24, 0.26, 0.22, 0.14, 0.08, 0.06))[0]
        sample = rng.sample(products, k=min(k, len(products)))
        items = schema.build_order_items(order_id, sample, item_id, rng)
        for it in items:
            sink.write_row("order_items", it)
        item_id += len(items)
        counts["order_items"] += len(items)

        order_total = round(sum(it["net_amount"] for it in items), 2)
        pay = schema.build_payment(payment_id, order, order_total, rng)
        sink.write_row("payments", pay)
        payment_id += 1
        counts["payments"] += 1

        if progress and order_id % 100_000 == 0:
            print(f"  ... {order_id:,} orders", file=sys.stderr)

    return counts


# --------------------------------------------------------------------------- #
# CDC mutator: emit realistic UPDATE/INSERT/DELETE traffic
# --------------------------------------------------------------------------- #


def mutate(dsn: str, rate: int, seconds: int, rng: random.Random):
    """Advance random in-flight orders through their lifecycle to emit CDC events."""
    try:
        import psycopg
    except ImportError as e:  # pragma: no cover
        raise SystemExit("psycopg not installed. Run: pip install '.[postgres]'") from e

    conn = psycopg.connect(dsn, autocommit=True)
    deadline = time.time() + seconds
    transitions = {
        schema.STATUS_PLACED: schema.STATUS_PAID,
        schema.STATUS_PAID: schema.STATUS_SHIPPED,
        schema.STATUS_SHIPPED: schema.STATUS_DELIVERED,
    }
    print(f"mutating ~{rate} orders/s for {seconds}s ...", file=sys.stderr)
    n = 0
    while time.time() < deadline:
        with conn.cursor() as cur:
            for cur_status, next_status in transitions.items():
                cur.execute(
                    """
                    UPDATE orders SET status = %s, updated_at = now()
                    WHERE order_id IN (
                        SELECT order_id FROM orders WHERE status = %s
                        ORDER BY random() LIMIT %s
                    )
                    """,
                    (next_status, cur_status, max(rate // 3, 1)),
                )
                n += cur.rowcount
        time.sleep(1.0)
    conn.close()
    print(f"done: {n:,} status transitions emitted", file=sys.stderr)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="novamart-gen", description=__doc__)
    sub = p.add_subparsers(dest="cmd")

    # default (generate) args live on the top-level parser too
    p.add_argument("--sink", choices=("csv", "postgres"), default="csv")
    p.add_argument(
        "--scale",
        type=float,
        default=0.01,
        help="1.0 => ~5.4M order items; 0.01 => a quick local sample",
    )
    p.add_argument("--out", default="./data", help="output dir for --sink csv")
    p.add_argument(
        "--dsn", default=os.environ.get("NOVAMART_DSN"), help="Postgres DSN for --sink postgres"
    )
    p.add_argument("--seed", type=int, default=SEED)

    m = sub.add_parser("mutate", help="emit continuous CDC change events")
    m.add_argument("--dsn", default=os.environ.get("NOVAMART_DSN"), required=False)
    m.add_argument("--rate", type=int, default=30, help="approx status updates per second")
    m.add_argument("--seconds", type=int, default=300)
    m.add_argument("--seed", type=int, default=SEED)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rng = random.Random(args.seed)

    if args.cmd == "mutate":
        if not args.dsn:
            raise SystemExit("--dsn (or NOVAMART_DSN) required for mutate")
        mutate(args.dsn, args.rate, args.seconds, rng)
        return 0

    cfg = ScaleConfig(scale=args.scale)
    fk = _faker()

    if args.sink == "csv":
        sink = CsvSink(args.out)
    else:
        if not args.dsn:
            raise SystemExit("--dsn (or NOVAMART_DSN) required for --sink postgres")
        sink = PostgresSink(args.dsn)

    t0 = time.time()
    print(
        f"generating scale={args.scale} "
        f"(customers={cfg.customers:,} products={cfg.products:,} orders={cfg.orders:,})",
        file=sys.stderr,
    )
    try:
        counts = generate_all(cfg, sink, rng, fk)
    finally:
        sink.close()
    dt = time.time() - t0
    total = sum(counts.values())
    print(
        f"done in {dt:,.1f}s — {total:,} rows: "
        + ", ".join(f"{k}={v:,}" for k, v in counts.items()),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
