# NovaMart Lakehouse — common tasks
.PHONY: help install up down seed cdc-register mutate test lint fmt dbt app

help:
	@echo "install       install python deps (editable + dev)"
	@echo "up / down     start / stop the local docker stack"
	@echo "seed          generate a small sample into Postgres (scale 0.02)"
	@echo "seed-big      generate the full 5M+ dataset into Postgres (scale 1.0)"
	@echo "cdc-register  register the Debezium Postgres connector"
	@echo "mutate        emit continuous CDC change events for 5 min"
	@echo "test lint fmt run pytest / ruff / black"
	@echo "app           run the Streamlit homepage"

install:
	pip install -e ".[dev,postgres]"

up:
	cd platform/docker && docker compose up -d

down:
	cd platform/docker && docker compose down

seed:
	python -m novamart_gen.generate --sink postgres --scale 0.02 \
		--dsn postgresql://nova:nova@localhost:5432/novamart

seed-big:
	python -m novamart_gen.generate --sink postgres --scale 1.0 \
		--dsn postgresql://nova:nova@localhost:5432/novamart

sample:
	python -m novamart_gen.generate --sink csv --scale 0.01 --out data/sample

cdc-register:
	curl -s -X POST -H "Content-Type: application/json" \
		--data @platform/docker/connectors/debezium-postgres.json \
		http://localhost:8083/connectors

mutate:
	python -m novamart_gen.generate mutate \
		--dsn postgresql://nova:nova@localhost:5432/novamart --rate 50 --seconds 300

test:
	pytest -q

lint:
	ruff check .

fmt:
	black .

dbt:
	cd transform && dbt build --target dev

app:
	streamlit run app/streamlit_app.py
