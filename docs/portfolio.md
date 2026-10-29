# Portfolio and resume copy

## Project card

**SignalFlow — Grid intelligence, from source to decision.**

An observable Python data platform that ingests public grid signals, validates and stores historical observations, and serves carbon-aware infrastructure analytics through FastAPI and an interactive dashboard. Includes replay-safe processing, SQL analytics, tests, and optional Kafka/dbt/Airflow deployment components.

Tags: Python · SQL · FastAPI · Data pipelines · Data quality · Infrastructure analytics.

## Short introduction

I am building data platforms, backend services and analytical tools, informed by my background in computational cognitive science, computer science and designing complex technical products. SignalFlow is my first independent engineering portfolio project: a complete local pipeline with real public data, reproducible analytics and explicit operational evidence.

Verify personal education and employment wording against the final resume before publishing. Do not invent additional completed projects. This repository is separate from the existing product design portfolio; it includes a single technical case-study page, not a replacement multi-project portfolio.

## Data engineering resume version

- Built a Python ingestion pipeline for NESO grid signals with bounded retries, UTC backfills, transactional materialization and content-based deduplication; verified a 672-event live-data backfill and replay with zero duplicate insertions.
- Implemented an optional Kafka transport with manual offset commits, dead-letter handling and a shared PostgreSQL-compatible sink; added failure-semantics unit tests and container integration configuration.

## Data analytics resume version

- Analyzed seven days of observed grid data using SQL and Python, exposing forecast MAE, renewable generation share, source freshness and historical carbon-intensity variation in an interactive dashboard.
- Built a unit-explicit compute emissions explorer that compares contiguous observed windows and rejects missing data; distinguished historical estimates from realized operating savings.

## Analytics engineering resume version

- Defined source contracts and dbt staging/daily-mart models for grid intensity and forecast residuals, with uniqueness, nullability, interval and generation-balance assertions.
- Documented metric semantics, nullable observations, UTC aggregation and lineage; included a CI warehouse build and an Airflow reconciliation DAG verified in the local container deployment.

## Software engineering resume version

- Built and tested a modular FastAPI backend, operational CLI and responsive dashboard with parameter validation, read-only CSV export, database readiness checks and Prometheus metrics.
- Implemented replay-safe storage, source-failure recovery and deterministic historical workload calculations, with isolated API, analytics and transport-semantics tests.

## Publishing checklist

Use the real screenshot and measured verification file. Link a public repository only after one exists. Local Docker integration passed; cite `integration-evidence.json` and distinguish it from remote CI and production hosting. Do not claim a cloud deployment, performance benchmark, trained AI model, production scale, reduced energy bill or employment experience from this project. Add new measured evidence when it is obtained.
