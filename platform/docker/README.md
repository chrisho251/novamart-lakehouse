# Local plane — Docker

Brings up the source database, the CDC streaming bus, and the object-storage
landing zone.

| Service | Port | Purpose |
|---|---|---|
| Postgres | 5432 | OLTP source (logical replication on) |
| Kafka | 9092 | change-event bus (KRaft, no ZooKeeper) |
| Kafka Connect (Debezium) | 8083 | CDC connector REST API |
| MinIO | 9000 / 9001 | S3-compatible landing zone / console |
| Kafka UI | 8080 | inspect topics & connectors |

## Bring up

```bash
docker compose up -d
docker compose ps          # wait until healthy
```

## Register the CDC connector

```bash
curl -s -X POST -H "Content-Type: application/json" \
  --data @connectors/debezium-postgres.json \
  http://localhost:8083/connectors | jq .

# status
curl -s http://localhost:8083/connectors/novamart-postgres-cdc/status | jq .
```

Debezium takes an initial snapshot, then tails the WAL. Change events land on
topics `nova.public.<table>` (e.g. `nova.public.orders`).

## Generate change traffic

```bash
# seed some data first (from repo root)
python -m novamart_gen.generate --sink postgres --scale 0.02 \
  --dsn postgresql://nova:nova@localhost:5432/novamart

# then continuously advance order statuses -> UPDATE events on the WAL
python -m novamart_gen.generate mutate \
  --dsn postgresql://nova:nova@localhost:5432/novamart --rate 50 --seconds 300
```

Watch them arrive in Kafka UI (http://localhost:8080) or with the console
consumer.

## Tear down

```bash
docker compose down          # keep volumes
docker compose down -v       # wipe data + minio + kafka state
```
