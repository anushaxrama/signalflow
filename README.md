# SignalFlow

SignalFlow collects Great Britain's national grid carbon-intensity and generation-mix data, stores the original source events, and serves a dashboard for comparing forecasts with observed results. It also calculates the emissions associated with running a fixed electrical workload during different historical time windows.

The project deals with several problems that show up in data pipelines: actual values arrive after forecasts, upstream records can change, requests fail, and consumers may process the same event more than once. The ingestion code handles those cases without replacing missing observations with zero or counting an exact replay as new data.

![SignalFlow dashboard](docs/screenshots/dashboard.png)

[Build checks](https://github.com/anushaxrama/signalflow/actions/workflows/ci.yml) | [Architecture](docs/architecture.md) | [Runbook](docs/runbook.md) | [Verification](docs/verification.md)

## What it does

- Fetches carbon-intensity forecasts, observed intensity, and generation percentages from the public NESO Carbon Intensity API.
- Retains each distinct source payload with its content hash, processing decision, and provenance.
- Updates interval-level tables when source records change, including delayed actuals and revised fuel mixes.
- Shows observed intensity, forecast error, renewable share, missing actuals, unusual readings, and data freshness.
- Compares contiguous historical windows for a workload defined by IT power, duration, and power usage effectiveness (PUE).
- Supports direct ingestion into SQLite or PostgreSQL, plus an optional Kafka producer and consumer.
- Builds a separate dbt analytical layer and runs daily reconciliation through Airflow.

The dashboard uses HTML, CSS, JavaScript, and SVG. It does not need a frontend build step. The Python application uses FastAPI, SQLAlchemy, HTTPX, and Uvicorn. The container setup adds PostgreSQL 16, Kafka 3.9, dbt, and Airflow 2.10.

## Run locally

Use Python 3.12 and `make`. The test matrix also covers Python 3.9. This path uses SQLite and does not require Docker or an API key.

```sh
git clone https://github.com/anushaxrama/signalflow.git
cd signalflow
make setup
make ingest
make serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). `make ingest` fetches the preceding seven days. The SQLite database is created under `data/`, which is excluded from Git.

Start the polling worker in another terminal:

```sh
make worker
```

The worker fetches the preceding two days every five minutes. Re-reading recent history allows delayed actuals and source revisions to reach the database. The browser refreshes stored results every minute; refreshing the page does not ingest source data.

NESO observations use half-hour intervals. A five-minute polling schedule does not make this a subsecond telemetry feed.

If `make` is unavailable, run the equivalent commands:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m signalflow.cli ingest --days 7
.venv/bin/python -m signalflow.cli serve
```

## Run with PostgreSQL and Docker

Docker Engine or Docker Desktop with Compose is required. Choose one regular ingestion path: direct polling or Kafka.

### Direct polling

```sh
docker compose --profile polling up --build -d
docker compose run --rm api python -m signalflow.cli ingest --days 7
```

The API is available on port 8000. If another process already uses it:

```sh
SIGNALFLOW_PORT=8001 docker compose --profile polling up --build -d
```

PostgreSQL is reachable by the containers but has no published host port. Its data persists in a named volume. The credentials in Compose are local development values.

### Kafka ingestion

```sh
docker compose --profile streaming up --build -d
```

This starts the broker, topic initialization, producer, consumer, PostgreSQL, and API. The producer polls every five minutes. Topic `signalflow.grid.v1` has three partitions; `signalflow.deadletter.v1` holds rejected messages.

For a seven-day backfill through Kafka:

```sh
docker compose --profile streaming run --rm --entrypoint python producer -m signalflow.cli produce --days 7
```

The producer service normally runs a shell polling loop, so this one-off command overrides its entrypoint. Avoid enabling both the polling and streaming profiles for routine ingestion. The database deduplicates replays, but two producers would make redundant upstream requests.

### Airflow and dbt

```sh
docker compose --profile polling --profile orchestration up --build -d
```

Airflow's local UI is at [http://127.0.0.1:8080](http://127.0.0.1:8080). Read its startup logs for the generated standalone login details:

```sh
docker compose logs airflow
```

The `signalflow_reconcile` DAG runs daily at 06:00 UTC with historical catchup disabled. It reconciles seven days, runs `dbt build`, and checks dataset freshness. Failed tasks have two retries. Airflow, the pipeline, and dbt use separate Python environments to avoid dependency conflicts.

## Processing and recovery

The direct and Kafka paths share the same materializer:

```text
NESO API -> HTTP collection -> validation and content hash -> database transaction
                         \-> Kafka -> consumer ----------/

Stored observations -> FastAPI -> dashboard and CSV export
                    \-> dbt staging -> daily analytical mart
```

A source event's identity is a SHA-256 hash of its kind and canonical payload. The raw event claim and its analytical projections commit in one transaction. Reprocessing the same payload is a no-op. A changed payload is retained as a distinct event and can revise the corresponding interval.

A forecast-only record cannot erase a stored actual. A revised generation record replaces the interval's complete fuel mix so superseded fuel rows do not remain in the table.

The Kafka consumer commits its offset after durable database processing and, for rejected records, successful dead-letter publication. A crash between the database commit and offset commit causes a replay that the sink can deduplicate. Database writes and Kafka offsets do not share a transaction, and dead-letter messages can be delivered more than once.

HTTP requests use timeouts and bounded retries. An upstream outage leaves previously committed data available and records the direct run's failure. The worker retries on its next cycle. Invalid records remain inspectable in raw storage and do not enter the analytical tables.

## Stored data

| Relation | Grain and purpose |
| --- | --- |
| `raw_events` | One distinct source payload, with acceptance or rejection details |
| `observations` | One UTC interval, with forecast, nullable actual, and source-event reference |
| `generation` | One interval and fuel type, with percentage and source-event reference |
| `pipeline_runs` | One direct ingestion attempt, with counts, status, and failure details |
| `analytics.stg_grid_intervals` | Typed interval data and forecast residuals |
| `analytics.mart_grid_daily` | Daily observed coverage, intensity statistics, and forecast MAE |

The API calculates its metrics from the base tables. The dbt models are a separate analytical layer. Kafka consumption does not create entries in the direct-ingestion `pipeline_runs` table.

## Reading the dashboard

Carbon intensity is measured in grams of CO2 per kWh. Forecast and actual are stored separately. Forecast MAE excludes intervals without actual values. Actual coverage measures the share of stored intervals that have actuals; it does not prove that every expected source interval is present.

Renewable share means wind, solar, and hydro in this application. Biomass is excluded from that definition.

The anomaly calculation compares an actual with up to 48 preceding stored observations. It requires at least 12 prior actuals, uses a standard-deviation floor of 10, and flags an absolute z-score of at least 3. These flags identify readings to inspect, not confirmed grid incidents.

The workload calculator searches for fully observed, contiguous half-hour windows in the last seven days of stored data:

```text
Facility energy (kWh) = IT power (kW) * duration (hours) * PUE
Operational emissions (kg CO2) = facility energy * mean intensity / 1000
```

Its lowest and highest windows are hindsight comparisons. They are not forecasts or promises of future savings. The calculation excludes embodied emissions and does not include electricity prices, GPU utilization, or site-specific electricity contracts.

## API

| Endpoint | Response |
| --- | --- |
| `/api/overview?hours=48` | Metrics, interval series, generation mix, anomalies, direct runs, and recent quarantines |
| `/api/scenario?power_kw=100&duration_hours=2&pue=1.2` | Lowest and highest eligible historical workload windows |
| `/api/export.csv?hours=168` | Interval CSV with source-event references |
| `/health` | Database connectivity; returns 503 if unavailable |
| `/metrics` | Prometheus metrics for interval count, rejections, and freshness |
| `/docs` | Interactive OpenAPI documentation |
| `/case-study` | Project walkthrough |

Overview and export windows accept 6 through 720 hours. Scenario durations accept 0.5 through 24 hours in half-hour increments. All stored interval timestamps are UTC. Display windows are relative to the latest stored interval, so old data remains visible with a stale status.

## Configuration and operational checks

| Variable | Default or use |
| --- | --- |
| `DATABASE_URL` | `sqlite:///data/signalflow.db` for native execution; Compose supplies PostgreSQL |
| `POLL_SECONDS` | `300`; the native worker requires at least 60 seconds |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` for native Kafka commands; `kafka:9092` inside Compose |
| `SIGNALFLOW_PORT` | `8000`; changes the Compose API's host port |

Native commands read process environment variables. They do not automatically load `.env`. The example file contains container-oriented connection values; `postgres` and `kafka` are Compose service names.

```sh
make check
.venv/bin/python -m signalflow.cli ingest --days 30
docker compose logs -f worker
```

`check` exits nonzero for empty, stale, or degraded datasets. Freshness is based on the latest interval end, not the fetch time. Both intensity and generation must be within 90 minutes. This is a data-health check, not proof that every Kafka service is running. Backfills accept 1 through 30 days per invocation.

## Tests and recorded results

```sh
make test
```

The deterministic tests cover ingestion, revised payloads, missing actuals, validation, retries, failure records, anomaly calculations, scenario units and gaps, API responses, CSV output, and Kafka offset/dead-letter behavior. Unit-level Kafka checks use test doubles; the separate integration evidence records execution against a real broker.

The recorded local checks include:

- 37 tests passing against SQLite and against a separate PostgreSQL test database.
- A seven-day direct backfill with 672 unique events, 336 intensity intervals, 3,024 fuel rows, and no rejected records. Exact replay created no new events.
- A separate Kafka run that replayed 674 stored events without adding raw events and reached zero consumer lag on all three partitions.
- Two dbt models and 12 passing data tests.
- A successful three-task Airflow reconciliation, including a recorded scheduled run.

These are captured development runs, not fixed counts for a live upstream feed. See [source verification](docs/verification-data.json) and [container integration evidence](docs/integration-evidence.json).

[GitHub Actions](https://github.com/anushaxrama/signalflow/actions/workflows/ci.yml) runs SQLite and PostgreSQL tests on Python 3.9 and 3.12, validates Compose and application syntax, and builds the dbt models against a separate CI database. A passing CI run does not replace the recorded real-broker or scheduler checks.

## Limitations and next steps

The running stack is a local development deployment. Cloud hosting, sustained throughput, high availability, external alert delivery, and recovery from infrastructure loss have not been demonstrated. The single-broker Kafka setup has a replication factor of one. SQLAlchemy creates the initial schema; later schema changes need explicit migrations.

Before hosting the application, add access controls, TLS, managed secrets, tested backups, and infrastructure monitoring. The full Kafka and Airflow stack needs persistent compute. The [runbook](docs/runbook.md) covers recovery and deployment preparation.

## Repository layout

```text
signalflow/       Source collection, materialization, analytics, CLI, API, and static UI
analytics/        dbt models, tests, profiles, and pinned warehouse dependencies
orchestration/    Airflow DAG and isolated container environments
scripts/          CI seed and integration-evidence collection
tests/            Deterministic tests and captured public-source fixtures
docs/             Architecture, SQL, runbook, screenshots, and execution evidence
```

## Data source

Source data comes from the [NESO Carbon Intensity API](https://api.carbonintensity.org.uk/), covering Great Britain's national grid. The data is licensed under CC BY 4.0. Preserve source attribution when sharing extracts. Endpoint definitions are available in the [official API documentation](https://carbon-intensity.github.io/api-definitions/).
