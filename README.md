# NovaMart Lakehouse

An end-to-end **e-commerce data platform** built as a portfolio project:
batch + change-data-capture (CDC) ingestion of **5M+** transactional rows, a
**medallion lakehouse** on Databricks, a Kimball **star schema** built with dbt,
a live **analytics homepage**, and full **CI/CD** — all on free tiers.

> 📐 **Design doc + diagrams:** [`docs/architecture.html`](docs/architecture.html)
> (architecture, CDC flow, star schema, CI/CD).

---

## What this demonstrates

| Capability | How |
|---|---|
| Batch ingestion | PySpark JDBC bulk load Postgres → object storage → Delta bronze |
| CDC / streaming | Postgres WAL → Debezium → Kafka → Spark Structured Streaming → Delta `MERGE` |
| Lakehouse | Databricks Free Edition, Unity Catalog, Delta, medallion (bronze/silver/gold) |
| Dimensional modeling | dbt star schema, SCD-2 dimensions, tests + docs |
| Serving | Databricks SQL warehouse → Streamlit dashboard |
| Delivery | GitHub Actions (lint, pytest, dbt build) + Databricks Asset Bundles |

## Architecture at a glance

```
 LOCAL DOCKER PLANE                         │ CLOUD LAKEHOUSE (Databricks Free)
 ─────────────────────────────────────────  │ ─────────────────────────────────
 Postgres (OLTP, 5M+)                        │
   ├─ WAL → Debezium → Kafka → Spark stream ─┼─▶ Object storage ─▶ Bronze ─▶ Silver ─▶ Gold (dbt star)
   └─ JDBC ──────────── Spark batch ─────────┘   (MinIO/S3)        Delta     Delta     Delta ─▶ SQL ─▶ Streamlit
```

The **object-storage landing zone is the seam**: Databricks Free Edition is
serverless-only with restricted outbound networking, so the streaming plane runs
locally and hands off through S3-compatible storage — the same decoupling real
teams use.

## Repository layout

```
novamart-lakehouse/
├─ ingestion/
│  ├─ generator/      # Faker-based 5M+ synthetic seed  (pure-python, tested)
│  ├─ batch/          # PySpark JDBC bulk ingest → bronze
│  └─ streaming/      # Spark Structured Streaming CDC consumer → bronze
├─ transform/         # dbt project (staging → silver → gold star schema)
├─ platform/
│  ├─ docker/         # docker-compose: Postgres + Kafka + Connect + MinIO
│  ├─ databricks/     # Databricks Asset Bundle (jobs, workflows)
│  └─ terraform/      # optional: S3 + Unity Catalog objects
├─ app/               # Streamlit analytics homepage
├─ tests/             # pytest
└─ .github/workflows/ # CI/CD
```

## Quickstart (local)

```bash
# 0. Python deps (generator + tests)
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 1. Bring up the source + streaming stack
cd platform/docker && docker compose up -d

# 2. Seed the OLTP database (small run; use --scale 1.0 for 5M+)
python -m novamart_gen.generate --sink postgres --scale 0.02 \
  --dsn "postgresql://nova:nova@localhost:5432/novamart"

# 3. Register the Debezium CDC connector
curl -s -X POST -H "Content-Type: application/json" \
  --data @platform/docker/connectors/debezium-postgres.json \
  http://localhost:8083/connectors | jq .

# 4. Run the streaming CDC consumer (Spark)
spark-submit ingestion/streaming/cdc_stream.py

# 5. Build the star schema
cd transform && dbt build --target dev
```

See per-directory READMEs for details. Numbers, DSNs, and scale are configurable.

## Dashboard (multi-page)

A Streamlit app (`app/`, uses `st.navigation`) with six pages, sharing one data
layer and global sidebar filters (date / region / category / segment):

| Page | Shows |
|---|---|
| **Overview** | net revenue, orders, AOV, margin, revenue trend, region & category, funnel |
| **Sales & revenue** | category-over-time, YoY, price-band mix, seasonality, discount impact |
| **Customers** | segments, **cohort retention heatmap**, new vs returning, LTV distribution |
| **Operations** | status funnel, cancel/return rates, fulfillment mix, top sellers |
| **Payments** | method share, captured vs pending, installments, method over time |
| **Pipeline health** | row volumes, freshness, **automated data-quality checks** |

It runs against Databricks SQL (gold star schema) when credentials are set, and
otherwise against the local CSV sample — so it's demoable with zero cloud setup:

```bash
pip install -e ".[app]"
python -m novamart_gen.generate --sink csv --scale 0.01 --out data/sample
streamlit run app/streamlit_app.py
```

Every page is smoke-tested in CI via Streamlit's `AppTest` (`tests/test_app.py`).

## Cost

**$0.** Every component is OSS or a persistent free tier. See the cost table in
the [design doc](docs/architecture.html).

## License

MIT — sample/portfolio project. Data is fully synthetic.
