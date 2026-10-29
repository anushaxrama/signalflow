# Operations and deployment

## Local startup

```sh
make setup
make ingest
make serve
# In another terminal, keep source records current:
make worker
```

Open http://127.0.0.1:8000. The API is read-only and bound to loopback by default. `/docs` is the interactive API reference. `/health` checks database reachability, `/metrics` exposes Prometheus text metrics, and `python -m signalflow.cli check` exits nonzero when datasets are empty, stale or degraded. Dashboard refreshes stored data every 60 seconds; it does not trigger source ingestion.

## PostgreSQL + polling

Requires Docker Engine/Desktop and Compose v2. Docker Desktop has been installed on this Mac. If a new terminal cannot find Docker or its credential helper, use this command-scoped setup:

```sh
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

Use `SIGNALFLOW_PORT=8001 docker compose ...` when the original SQLite server occupies port 8000. The verified container API is currently running on 8001.

```sh
docker compose --profile polling up --build -d
# Optional longer initial backfill:
docker compose run --rm api python -m signalflow.cli ingest --days 7
docker compose logs -f worker
```

API is at http://127.0.0.1:8000. Database credentials in Compose are **local development values**. PostgreSQL has no host port published. Volumes persist across ordinary `docker compose down`. Keep `down -v` for intentionally discarding all local container data.

## Kafka streaming path

```sh
docker compose --profile streaming up --build -d
```

The producer service overrides its entrypoint for continuous polling. Use this override for a one-off historical backfill:

```sh
docker compose --profile streaming run --rm --entrypoint python producer -m signalflow.cli produce --days 7
```

Topic creation is explicit and automatic through `kafka-init`. Broker storage is persistent. Inspect offsets with:

```sh
docker compose --profile streaming exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --describe --group signalflow-materializer-v1
```

If the consumer is failing, check PostgreSQL first. Database exceptions intentionally prevent offset commits. After fixing a validation issue, write a **corrected** payload (with a new content hash); the original rejected event remains immutable. Resetting offsets replays existing accepted/rejected records without changing their decision. DLQ messages are evidence, not a retry queue.

## Airflow + dbt

```sh
docker compose --profile polling --profile orchestration up --build -d
# Retrieve Airflow standalone generated login information from local logs:
docker compose logs airflow
```

Airflow UI is loopback-only at http://127.0.0.1:8080. The standalone deployment is a local demonstration, not a multi-node production scheduler. Daily DAG runs at 06:00 UTC, retries failed tasks twice and disables historical catchup. It backfills seven days, builds/tests dbt, then checks freshness. Airflow 2, the pipeline and dbt use separate Python environments to avoid dependency conflicts. The dbt executable inside the container is `/home/airflow/dbt-venv/bin/dbt`.

Manual warehouse build without Airflow, with PostgreSQL reachable from the host:

```sh
python3 -m venv .dbt-venv
.dbt-venv/bin/pip install 'dbt-postgres>=1.9,<2'
# Set DBT_HOST and DBT_PASSWORD in your terminal, then:
.dbt-venv/bin/dbt build --project-dir analytics --profiles-dir analytics
```

Compose does not publish PostgreSQL to the host; run dbt through Airflow's container, or configure a host-accessible PostgreSQL instance. Model freshness and coverage need business thresholds per downstream use; source `ingested_at` is stored as text, so no misleading native dbt timestamp-freshness check is declared.

## Monitoring and recovery

1. `/health` 503: inspect connection settings and database availability.
2. `/api/overview` stale: compare interval end with current UTC, inspect upstream API and worker logs. Re-fetching old data does not reset interval age.
3. Degraded run: inspect `pipeline_runs.error` and `raw_events where status='rejected'`. Valid records before a source failure are retained.
4. Forecast-only intervals: wait for upstream actuals; do not fill them with zero or forecasts in observed metrics.
5. Worker termination: SIGINT/SIGTERM stops polling after the current operation; ordinary restarts use idempotent sinks.
6. Backfill after outage: run `ingest --days N` (maximum 30); larger history requires several explicitly dated source windows or an extension of the CLI.
7. SQLite backup: stop writers and copy the database with SQLite backup tooling. PostgreSQL: use `pg_dump` with managed credentials. Test restoration before relying on backups.

Suggested Prometheus alerts: `signalflow_data_healthy == 0` sustained 15 minutes, `signalflow_interval_age_seconds > 5400`, increase in `signalflow_rejected_events_total`. `/metrics` computes a small bounded snapshot; use caching or separate exporters at higher scrape volume. Broker lag and process liveness require infrastructure exporters; neither is implied by dataset health.

## Hosted deployment preparation

The container runs as a nonroot user and has a database health check. For a persistent VM/container host, provision PostgreSQL, configure `DATABASE_URL`, run API and polling worker as separate services, add TLS and access controls through a reverse proxy, use managed secrets and backups, and configure alert delivery. Kafka and Airflow need persistent compute and independent state; static Sites/Cloudflare Worker hosting cannot run this complete topology.

No paid resources, public endpoint, GitHub repository, or cloud deployment were created. The local Docker deployment has passed PostgreSQL, Kafka, dbt and Airflow runtime checks. GitHub Actions workflows are included but have not run remotely; no cloud deployment or production-scale benchmark is claimed. See `docs/integration-evidence.json`.


## Stop the local containers

```sh
docker compose --profile streaming --profile orchestration stop
```

This preserves the PostgreSQL, Kafka and Airflow volumes. One-shot Kafka ownership/topic initializer containers are expected to show Exited (0); they are not failed services. The broker runs as UID 1000 after its dedicated volume initializer prepares ownership.
