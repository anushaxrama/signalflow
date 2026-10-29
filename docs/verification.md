# Verification report

Build date: October 27, 2026, America/Los_Angeles (source and database timestamps use UTC).

## Executed successfully

- **Real source ingestion:** seven daily requests per dataset to the NESO public API; 672 accepted raw events, 336 intensity intervals, 3,024 fuel rows, zero rejected events. No credentials or synthetic dashboard data.
- **Exact replay:** reprocessed all 672 stored source payloads; zero inserted events, zero rejections; observations remained at 336. Captured output: [verification-data.json](verification-data.json).
- **Automated suite:** 37 tests passed locally on Python 3.9.6. Covers domain validation, null actuals, timestamp contracts, revised mix replacement, actual preservation, serial and concurrent deduplication, source retry/exhaustion, durable partial failures, historical scenario units/gaps, rolling anomalies without lookahead, interval freshness, API validation, CSV, metrics, case-study response, and simulated Kafka commit/dead-letter behavior.
- **Browser:** the running FastAPI dashboard rendered real data; changing 48 hours to seven days changed interval count from 96 to 336 and recalculated MAE from 8.9 to 8.7 gCO₂/kWh. Scenario form returned 12.24 / 46.26 / 34.02 kgCO₂ for lowest/highest/difference in the captured sample.
- **Mobile browser:** tested 390 × 844 viewport; fixed navigation overflow and verified page width equals viewport width (390 px). Chart resizes with the viewport. Screenshot: [mobile.png](screenshots/mobile.png).
- **API documentation:** Swagger UI loaded from the local server and displayed all public endpoints.
- **Case-study page:** opened in the browser and verified visible content and screenshot.
- **dbt parsing:** `dbt parse --no-partial-parse` succeeded using dbt-core 1.10.23 / postgres adapter 1.9.1 in an isolated Python environment, with anonymous usage statistics disabled. This validates model/source/test configuration and Jinja parsing, not PostgreSQL SQL execution.
- **Static checks:** JavaScript syntax checked with Node; Python modules compiled with a writable bytecode-cache directory; deployment/dbt/CI YAML parsed successfully. Documentation relative links checked.

Screenshots: [dashboard](screenshots/dashboard.png), [case study](screenshots/case-study.png).

## Docker follow-up: executed successfully

Docker Desktop 4.97.0 / Engine 29.9.2 was installed on this Apple Silicon Mac after the first local run. The complete Compose stack now runs locally. See [integration-evidence.json](integration-evidence.json) and [Docker Desktop screenshot](screenshots/docker-desktop.png).

- PostgreSQL 16: all 37 tests passed against an isolated `signalflow_test` database. This uncovered and fixed a driver row-count assumption; conflict claims now use `RETURNING`. The 37 SQLite tests still pass.
- Fresh deployment: the API and workers serialize PostgreSQL schema bootstrap with a transaction-scoped advisory lock. Kafka has a dedicated one-shot volume ownership initializer; the broker runs unprivileged.
- Real Kafka path: seven-day public-data backfill delivered to PostgreSQL. All three partitions reached zero lag. Replayed 674 exact stored raw events through Kafka; raw-event and observation counts were unchanged.
- dbt-core 1.12.6 / postgres adapter 1.11.0: executed two models and all 12 data tests successfully (14 successful nodes, zero warnings/errors), producing a daily mart.
- Airflow 2.10.5: DAG import errors empty; the complete three-task DAG test ran real reconciliation, dbt build and freshness checking, ending in success. The scheduler also completed an actual scheduled run with all three tasks successful; its heartbeat reported an alive job. Airflow, dbt and pipeline dependencies are isolated in separate environments.
- Container API: healthy on port 8001. Original SQLite demo remains on port 8000.

## Remaining limits

The included GitHub Actions workflow defines Python 3.9/3.12 tests against SQLite/PostgreSQL and a PostgreSQL dbt build. It has not been run on GitHub. No public repository, cloud resources, production deployment, distributed throughput measurements or operating savings are claimed.

## Reproduce

```sh
make setup
make test
make ingest
make serve
```

Run `make worker` separately for ongoing refresh. A fresh source pull will naturally change metrics; the verification JSON preserves the first captured evidence. Data acquisition depends on source/network availability. Source records are persisted locally in ignored `data/signalflow.db`; a clean clone must ingest before displaying data.

## Interface refinement

The grid-observatory redesign was reviewed at 390 × 844, 1024 × 900 and 1440 × 1000. Checked widths had no horizontal page overflow. Local font files loaded successfully, and the reviewed dashboard emitted no browser errors or warnings. Browser checks exercised range tabs and mobile select, chart keyboard inspection and series visibility, the source-information dialog, edited-input invalidation, and workload recalculation (100 kW to 200 kW correctly doubled the estimated emissions). All 37 existing tests remained passing. Current screenshots replace the original interface captures. See [design notes](design.md).
