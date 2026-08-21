"""Batch ingestion: bulk-load Postgres tables to the bronze layer via Spark JDBC.

Two modes:
  * full        - read the whole table (used for dimensions and the initial load)
  * incremental - read only rows changed since a watermark (updated_at)

Runs on Databricks (writes managed Delta tables) or locally against MinIO/S3
with the Delta + Postgres JDBC jars on the classpath.

    spark-submit \
      --packages io.delta:delta-spark_2.12:3.2.0,org.postgresql:postgresql:42.7.3 \
      ingestion/batch/batch_ingest.py --mode full --tables customers,products,sellers

    spark-submit ... ingestion/batch/batch_ingest.py \
      --mode incremental --tables orders,order_items,payments --since 2024-12-01
"""

from __future__ import annotations

import argparse
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# table -> (has_updated_at_watermark, primary_key)
TABLE_META = {
    "customers": (True, "customer_id"),
    "sellers": (False, "seller_id"),
    "products": (True, "product_id"),
    "orders": (True, "order_id"),
    "order_items": (False, "order_item_id"),
    "payments": (True, "payment_id"),
}

BRONZE_DB = os.environ.get("BRONZE_DB", "novamart.bronze")
LANDING_URI = os.environ.get("LANDING_URI", "s3a://novamart-lake/bronze")


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("novamart-batch-ingest")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        # S3A (MinIO) settings are no-ops on Databricks, which uses its own creds.
        .config("spark.hadoop.fs.s3a.endpoint", os.environ.get("S3_ENDPOINT", ""))
        .config("spark.hadoop.fs.s3a.access.key", os.environ.get("S3_ACCESS_KEY", ""))
        .config("spark.hadoop.fs.s3a.secret.key", os.environ.get("S3_SECRET_KEY", ""))
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .getOrCreate()
    )


def jdbc_opts() -> dict:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "novamart")
    return {
        "url": f"jdbc:postgresql://{host}:{port}/{db}",
        "user": os.environ.get("POSTGRES_USER", "nova"),
        "password": os.environ.get("POSTGRES_PASSWORD", "nova"),
        "driver": "org.postgresql.Driver",
        "fetchsize": "10000",
    }


def read_table(spark, table: str, mode: str, since: str | None):
    opts = jdbc_opts()
    has_wm, pk = TABLE_META[table]

    if mode == "incremental" and has_wm and since:
        # push the predicate down to Postgres; parallelize by PK range
        query = f"(SELECT * FROM {table} WHERE updated_at >= '{since}') AS t"
        reader = spark.read.format("jdbc").options(**opts).option("dbtable", query)
    else:
        # parallel full read partitioned on the numeric PK
        bounds = (
            spark.read.format("jdbc")
            .options(**opts)
            .option("dbtable", f"(SELECT min({pk}) lo, max({pk}) hi FROM {table}) b")
            .load()
            .first()
        )
        lo, hi = (bounds["lo"] or 0), (bounds["hi"] or 1)
        reader = (
            spark.read.format("jdbc")
            .options(**opts)
            .option("dbtable", table)
            .option("partitionColumn", pk)
            .option("lowerBound", str(lo))
            .option("upperBound", str(hi))
            .option("numPartitions", "8")
        )
    return reader.load()


def write_bronze(df, table: str):
    # Harmonize with the CDC schema so downstream dbt staging is uniform across
    # both load paths (_deleted / _event_ts_ms / _op present on every bronze table).
    has_wm, _ = TABLE_META[table]
    event_ts = (
        (F.col("updated_at").cast("timestamp").cast("long") * 1000)
        if has_wm
        else (F.unix_timestamp(F.current_timestamp()) * 1000)
    )
    df = (
        df.withColumn("_op", F.lit("r"))
        .withColumn("_deleted", F.lit(False))
        .withColumn("_event_ts_ms", event_ts.cast("long"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("batch"))
    )
    target = f"{BRONZE_DB}.{table}"
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("path", f"{LANDING_URI}/{table}")
        .saveAsTable(target)
    )
    print(f"wrote {df.count():,} rows -> {target}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("full", "incremental"), default="full")
    ap.add_argument("--tables", default=",".join(TABLE_META), help="comma-separated")
    ap.add_argument("--since", default=None, help="watermark for incremental (ISO date)")
    args = ap.parse_args()

    spark = build_spark()
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {BRONZE_DB}")

    for table in [t.strip() for t in args.tables.split(",") if t.strip()]:
        if table not in TABLE_META:
            raise SystemExit(f"unknown table: {table}")
        print(f"[{args.mode}] ingesting {table} ...")
        df = read_table(spark, table, args.mode, args.since)
        write_bronze(df, table)

    spark.stop()


if __name__ == "__main__":
    main()
