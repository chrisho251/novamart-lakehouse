-- NovaMart OLTP schema (source of truth for both batch and CDC ingestion).
-- Kept intentionally normalized; the dimensional model is built downstream in dbt.

CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE IF NOT EXISTS customers (
    customer_id   BIGINT PRIMARY KEY,
    full_name     TEXT        NOT NULL,
    email         TEXT        NOT NULL,
    segment       TEXT        NOT NULL,
    city          TEXT,
    state         CHAR(2),
    region        TEXT,
    created_at    TIMESTAMP   NOT NULL,
    updated_at    TIMESTAMP   NOT NULL
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id        BIGINT PRIMARY KEY,
    seller_name      TEXT     NOT NULL,
    city             TEXT,
    state            CHAR(2),
    region           TEXT,
    fulfillment_type TEXT     NOT NULL,
    rating           NUMERIC(3,2),
    created_at       TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id    BIGINT PRIMARY KEY,
    product_name  TEXT          NOT NULL,
    category      TEXT          NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    unit_cost     NUMERIC(12,2) NOT NULL,
    created_at    TIMESTAMP     NOT NULL,
    updated_at    TIMESTAMP     NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id     BIGINT PRIMARY KEY,
    customer_id  BIGINT      NOT NULL REFERENCES customers (customer_id),
    seller_id    BIGINT      NOT NULL REFERENCES sellers (seller_id),
    status       TEXT        NOT NULL,
    order_ts     TIMESTAMP   NOT NULL,
    updated_at   TIMESTAMP   NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id BIGINT PRIMARY KEY,
    order_id      BIGINT        NOT NULL REFERENCES orders (order_id),
    product_id    BIGINT        NOT NULL REFERENCES products (product_id),
    quantity      INT           NOT NULL,
    unit_price    NUMERIC(12,2) NOT NULL,
    discount_pct  NUMERIC(4,3)  NOT NULL,
    net_amount    NUMERIC(14,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items (order_id);

CREATE TABLE IF NOT EXISTS payments (
    payment_id     BIGINT PRIMARY KEY,
    order_id       BIGINT        NOT NULL REFERENCES orders (order_id),
    payment_method TEXT          NOT NULL,
    installments   INT           NOT NULL DEFAULT 1,
    amount         NUMERIC(14,2) NOT NULL,
    status         TEXT          NOT NULL,
    paid_ts        TIMESTAMP
);

-- ------------------------------------------------------------------ CDC setup
-- Debezium needs the full row image on UPDATE/DELETE so before/after are complete.
ALTER TABLE customers   REPLICA IDENTITY FULL;
ALTER TABLE sellers     REPLICA IDENTITY FULL;
ALTER TABLE products    REPLICA IDENTITY FULL;
ALTER TABLE orders      REPLICA IDENTITY FULL;
ALTER TABLE order_items REPLICA IDENTITY FULL;
ALTER TABLE payments    REPLICA IDENTITY FULL;

-- Publication consumed by the Debezium pgoutput plugin.
DROP PUBLICATION IF EXISTS novamart_pub;
CREATE PUBLICATION novamart_pub FOR ALL TABLES;
