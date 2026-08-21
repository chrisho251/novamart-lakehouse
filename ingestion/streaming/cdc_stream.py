"""CDC streaming: consume Debezium change events from Kafka into bronze Delta.

Debezium (JSON, schemas disabled) emits one message per row change with an
envelope::

    { "op": "c|u|d|r", "ts_ms": ..., "before": {...}, "after": {...},
      "source": { "table": "orders", ... } }

For each micro-batch we upsert the latest state per primary key into a bronze
Delta table using ``MERGE``, which makes the pipeline idempotent under replays
and out-of-order delivery. Deletes (op=d) are soft-deleted with ``_deleted=true``.

    spark-submit \
      --packages io.delta:delta-spark_2.12:3.2.0,\
org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
      ingestion/streaming/cdc_stream.py --tables orders,order_items,payments
"""

from __future__ import annotations

import argparse
import os

from batch_ingest import TABLE_META  # reuse PK metadata  # noqa: E402
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC_PREFIX = os.environ.get("CDC_TOPIC_PREFIX", "nova.public")
BRONZE_DB = os.environ.get("BRONZE_DB", "novamart.bronze")
LANDING_URI = os.environ.get("LANDING_URI", "s3a://novamart-lake/bronze")
CHECKPOINT_URI = os.environ.get("CHECKPOINT_URI", "s3a://novamart-lake/_checkpoints")

# Minimal envelope schema (payload fields stay as a JSON string, parsed per table).
ENVELOPE = StructType(
    [
        StructField("op", StringType()),
        StructField("ts_ms", StringType()),
        StructField("before", StringType()),
        StructField("after", StringType()),
    ]
)


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("novamart-cdc-stream")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.hadoop.fs.s3a.endpoint", os.environ.get("S3_ENDPOINT", ""))
        .config("spark.hadoop.fs.s3a.access.key", os.environ.get("S3_ACCESS_KEY", ""))
        .config("spark.hadoop.fs.s3a.secret.key", os.environ.get("S3_SECRET_KEY", ""))
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.sql.streaming.schemaInference", "true")
        .getOrCreate()
    )


def ensure_bronze_table(spark: SparkSession, table: str, sample: DataFrame):
    """Create the bronze Delta table from an inferred schema if absent."""
    target = f"{BRONZE_DB}.{table}"
    if not spark.catalog.tableExists(target):
        (
            sample.limit(0)
            .write.format("delta")
            .option("path", f"{LANDING_URI}/{table}")
            .saveAsTable(target)
        )
    return target


def make_upsert_fn(spark: SparkSession, table: str):
    from delta.tables import DeltaTable

    _, pk = TABLE_META[table]

    def upsert(batch_df: DataFrame, batch_id: int):
        if batch_df.rdd.isEmpty():
            return

        parsed = (
            batch_df.select(F.from_json(F.col("value").cast("string"), ENVELOPE).alias("e"))
            .select("e.*")
            .where(F.col("op").isNotNull())
        )
        # Choose the row image: after for c/u/r (snapshot read), before for d.
        payload_col = F.when(F.col("op") == "d", F.col("before")).otherwise(F.col("after"))
        # Infer the payload schema from JSON in this batch.
        payload_schema = spark.read.json(
            parsed.select(payload_col.alias("p"))
            .where(F.col("p").isNotNull())
            .rdd.map(lambda r: r.p)
        ).schema

        rows = (
            parsed.withColumn("payload", F.from_json(payload_col, payload_schema))
            .select("op", "ts_ms", "payload.*")
            .withColumn("_deleted", F.col("op") == F.lit("d"))
            .withColumn("_op", F.col("op"))
            .withColumn("_event_ts_ms", F.col("ts_ms").cast("long"))
            .withColumn("_ingested_at", F.current_timestamp())
            .withColumn("_source", F.lit("cdc"))
            .drop("op", "ts_ms")
        )

        # Keep only the latest event per key within the batch (highest _event_ts_ms).
        from pyspark.sql.window import Window

        w = Window.partitionBy(pk).orderBy(F.col("_event_ts_ms").desc())
        latest = rows.withColumn("_rn", F.row_number().over(w)).where(F.col("_rn") == 1).drop("_rn")

        target = ensure_bronze_table(spark, table, latest)
        dt = DeltaTable.forName(spark, target)
        (
            dt.alias("t")
            .merge(latest.alias("s"), f"t.{pk} = s.{pk}")
            .whenMatchedUpdateAll(condition="s._event_ts_ms >= t._event_ts_ms")
            .whenNotMatchedInsertAll()
            .execute()
        )
        print(f"[{table}] batch {batch_id}: merged {latest.count()} keys")

    return upsert


def stream_table(spark: SparkSession, table: str):
    topic = f"{TOPIC_PREFIX}.{table}"
    stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .load()
    )
    return (
        stream.writeStream.foreachBatch(make_upsert_fn(spark, table))
        .option("checkpointLocation", f"{CHECKPOINT_URI}/{table}")
        .trigger(processingTime="30 seconds")
        .start()
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="orders,order_items,payments,customers,products,sellers")
    args = ap.parse_args()

    spark = build_spark()
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {BRONZE_DB}")

    queries = [stream_table(spark, t.strip()) for t in args.tables.split(",") if t.strip()]
    for q in queries:
        q.awaitTermination()


if __name__ == "__main__":
    main()
