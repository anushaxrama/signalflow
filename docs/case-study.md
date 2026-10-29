# SignalFlow: making public grid data useful for infrastructure decisions

**Independent engineering portfolio project · Python / SQL / FastAPI / data pipelines**

## Problem

A dashboard cannot make reliable decisions from stale, duplicated or ambiguous data. Carbon-aware compute adds another complication: published forecasts, observed actuals and modeled workload estimates are different things. SignalFlow makes those differences explicit while demonstrating the engineering behind a usable analytical product.

## What I built

A Python platform that backfills and polls the NESO Carbon Intensity API, preserves original events, validates their contracts, writes durable analytical records, and powers an operational dashboard. A historical workload explorer combines observed intensity with user-supplied IT power, duration and PUE to compare possible timing windows.

The local platform runs end to end with SQLite and FastAPI. The PostgreSQL/Kafka container path was also verified with real source data, zero-lag consumption and exact replay. dbt built both models and passed all 12 quality tests; all three Airflow DAG tasks completed successfully.

## Engineering decisions

**Start with a functioning vertical slice.** A real source, durable store, API and interactive product establish value before introducing broker/scheduler operations. The direct and Kafka paths share one validation/materialization function so correctness does not depend on transport.

**Treat source revisions as data.** Raw identities include content, while analytical identities use settlement intervals. Repeated payloads are deduplicated; changed observations remain auditable. A delayed forecast cannot erase a known actual, and generation revisions replace all fuels atomically.

**Use transactions at the actual boundary.** Raw claims and projections share a SQL transaction. Kafka offsets commit after durable processing. This provides idempotent at-least-once processing without claiming impossible atomicity across Kafka and the database.

**Preserve uncertainty in the product.** Actuals remain nullable. Forecast MAE excludes unknown actuals. Freshness is measured from source interval end. The calculator rejects incomplete/gapped windows and labels its results as hindsight estimates.

**Make operations inspectable.** Rejections carry validation errors; failed source requests produce durable run records; Prometheus metrics expose dataset age and quarantine counts. Statistical anomalies have a documented baseline and are not presented as proven incidents.

## Evidence from the first real-data run

The October 27, 2026 local run fetched 672 valid public events across seven days: 336 intensity intervals and 336 generation intervals, each with nine fuel records. All 672 events replayed with zero additional raw events. The seven-day observed forecast MAE was 8.7 gCO₂/kWh for that particular captured sample; this is source forecast accuracy, not a model trained by this project.

For a 100 kW IT workload lasting two hours at PUE 1.2, facility energy is 240 kWh. The captured dataset's lowest contiguous window averaged 51 gCO₂/kWh, giving 12.24 kgCO₂; the highest averaged 192.75, giving 46.26 kgCO₂. The 34.02 kg difference illustrates temporal sensitivity. It is not measured operating savings and does not establish a deployable scheduling policy.

Tests cover validation, exact replay, revisions, source outages, missing actuals, anomalies, scenario arithmetic, gaps, API boundaries, exports and simulated Kafka failure semantics. Browser checks confirm the dashboard, time filters and scenario form operate with real data. See the verification report for current counts and explicit unverified components.

## Skills demonstrated

| Track | Reviewable evidence |
| --- | --- |
| Data engineering | HTTP ingestion, UTC backfills, idempotent SQL sinks, Kafka producer/consumer, dead letters, retries and operational metadata |
| Data analytics | Explicit metric definitions, historical comparisons, SQL investigations, meaningful units and limitations |
| Analytics engineering | dbt staging/daily marts, quality assertions, typed timestamps, source contracts and reproducible SQL |
| Software engineering | Modular backend, API validation, CLI, tests, health checks, container configuration and responsive product |

## What comes next

Run the included CI suite on GitHub; add schema migrations before changing deployed tables; extend failure-injection coverage for broker outages and crash recovery; measure throughput on controlled hardware; add an authenticated hosted demo only after deployment integration passes. Extend to regional signals or electricity prices only with separate source contracts and clear licensing.

The existing product-design background contributes domain understanding and clarity in the dashboard. The project is presented as independent engineering work, with evidence and limitations, rather than professional data engineering experience.
