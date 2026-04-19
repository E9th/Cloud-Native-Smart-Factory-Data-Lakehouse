# Project Completion Report

Date: 2026-04-19
Project: Cloud-Native Smart Factory Data Lakehouse
Status: Completed

## 1. Executive Summary

This project delivered a complete cloud-native data pipeline for smart factory operations, from telemetry ingestion to analytics-ready dashboards.

The final implementation includes:
- Event ingestion via HTTP API and queue-based publisher
- Queue-to-lake batch landing in S3 with partitioned storage
- Snowflake RAW loading and validation workflows
- dbt staging and mart transformations with data quality tests
- Python analytics package for baseline, risk, and anomaly analysis
- Power BI operational dashboard with KPI and risk visualization

The project evolved through iterative troubleshooting and hardening across reliability, data quality, orchestration, and BI consumption.

## 2. End-to-End Workflow

### 2.1 Ingestion Layer (Producer)

1. Sensor events are generated from either:
- TypeScript generator service (continuous stream)
- HTTP API endpoint POST /api/sensor-data

2. Payloads are validated and published to RabbitMQ queue sensor_data_queue.

3. API service also exposes:
- GET /health for runtime and publish counters
- GET /api/dashboard for latest machine payload snapshots

Input payload schema:
- timestamp (ISO string)
- machine_id (string)
- temperature (number)
- vibration (number)

### 2.2 Landing Layer (Queue to Data Lake)

1. Python worker consumes messages from RabbitMQ.
2. Messages are parsed and batched in memory.
3. Batch flush conditions:
- batch_size messages reached
- flush_interval_seconds reached

4. Batch is written to local temp file (JSON or CSV).
5. File is uploaded to S3 partition path:
- sensor-data/year=YYYY/month=MM/day=DD/<file>

### 2.3 Warehouse RAW Layer (Snowflake)

1. Snowflake RAW tables receive data from S3 stage via COPY INTO.
2. MES data path is prepared through PostgreSQL source tables.
3. Orchestration path:
- Primary: Airflow DAG for extract/load tasks
- Fallback: PowerShell manual script when Airflow runtime is unavailable

4. RAW validation queries confirm row count growth and timestamp freshness.

### 2.4 Transformation Layer (dbt)

1. Source declarations map RAW_DATA tables.
2. Staging models perform standardization and quality hardening:
- trim/nullif for empty values
- key normalization (uppercase and regexp cleanup)
- deduplication via row_number

3. Mart models build business-facing outputs:
- fct_machine_health_hourly
- fct_work_orders_status
- fct_machine_risk_hourly

4. dbt tests enforce contracts:
- not_null
- unique
- accepted_values
- custom range test for machine_risk_score between 0 and 100

### 2.5 Analytics Layer (Python EDA)

1. Pull recent sensor data from Snowflake.
2. Build hourly features:
- rolling means/std (3h)
- rate of change
- anomaly rates

3. Compute machine baselines (p95 per machine with minimum thresholds).
4. Detect sustained temperature breaches.
5. Compute and rank machine risk scores.
6. Export artifacts for review and presentation.

### 2.6 BI Layer (Power BI)

1. Connect to Snowflake transformed views.
2. Build KPI cards and trend visuals.
3. Add risk chart and high-risk counters.
4. Align slicer behavior using shared time dimension (Dim_HOUR) so filters propagate consistently across facts.

## 3. Workflow by Project Phase

### Phase 2: Foundation and Baseline

Deliverables:
- API and generator connected to RabbitMQ
- S3 consumer in place
- Snowflake RAW load path verified
- k6 baseline load test executed

Outcome:
- Functional ingestion baseline established
- Performance and reliability gaps identified for hardening

### Phase 3: Secure Data Bridge and Orchestration

Deliverables:
- Storage integration and secure stage setup
- MES extract/load path into Snowflake RAW
- Airflow DAG assets prepared
- Manual fallback script implemented and verified

Outcome:
- Data movement complete even under orchestration runtime constraints

### Phase 4: Analytics and Decision Layer

Deliverables:
- dbt staging and marts complete
- Risk model implemented with thresholds and rolling features
- EDA outputs generated (correlation, breach events, risk ranking)
- Dashboard connected and KPI visuals delivered

Outcome:
- Portfolio-ready business-facing analytics layer delivered

## 4. Tech Stack and Why It Was Used

| Layer | Technology | Why it was used |
|---|---|---|
| Producer/API | TypeScript, Node.js, Express | Fast service development with strong typing for payload handling and API validation |
| Message Bus | RabbitMQ | Decouple producers/consumers and absorb burst traffic |
| Batch Worker | Python, pika, boto3 | Reliable queue consumption and S3 integration with straightforward batch control |
| Data Lake | AWS S3 | Durable, low-cost partitioned raw storage |
| Warehouse | Snowflake | Elastic compute and SQL-first analytics platform |
| Transformation | dbt | Versioned SQL models, dependencies, and repeatable tests |
| Orchestration | Airflow | Scheduled workflow and task-level dependency management |
| BI | Power BI | Rapid KPI dashboard and interactive filtering for operations teams |
| EDA | pandas, matplotlib, seaborn, snowflake-connector-python | Feature exploration, visualization, and reproducible analytics evidence |
| Performance Test | k6 | Load profile validation for API ingestion path |

## 5. Problems Encountered and Resolutions

### 5.1 Ingestion and Platform

Problem: API path did not consistently meet load thresholds at 1000 VUs.
- Symptom: request failures and p95 latency above target.
- Resolution: established baseline evidence, documented hardening need, separated performance tuning from functional milestone completion.

Problem: S3 and Snowflake secure bridge auth failures.
- Symptom: AssumeRole and AccessDenied errors.
- Resolution: corrected IAM trust policy and permissions using values from DESC STORAGE INTEGRATION.

Problem: SQL engine mismatch.
- Symptom: PostgreSQL script run in Snowflake produced function errors.
- Resolution: clarified runbook boundaries for PostgreSQL vs Snowflake execution contexts.

Problem: Airflow image pull/runtime instability.
- Symptom: Docker pull EOF/network failures blocked local Airflow startup.
- Resolution: used fallback script to keep delivery on track and validated Snowflake loads manually.

Problem: AWS CLI profile mismatch.
- Symptom: NoCredentials errors in fallback flow.
- Resolution: used verified profile and explicit environment/profile setup.

Problem: PowerShell generated malformed Snowflake COPY SQL.
- Symptom: positional columns like $1, $2 were interpolated unexpectedly.
- Resolution: preserved literals in template handling and only replaced named placeholders.

### 5.2 dbt Modeling and Validation

Problem: source declaration errors (dbt1005).
- Symptom: source not found in models.
- Resolution: fixed naming consistency, YAML indentation, and source identifiers.

Problem: test failures in staging and marts.
- Symptom: not_null, unique, and date null test failures.
- Resolution: added trim/nullif normalization, key cleaning, and dedup logic; added fallback date handling for work orders.

Problem: Cloud parser configuration mismatch.
- Symptom: stale dbt_project.yml content and parse failures.
- Resolution: synchronized branch content and replaced invalid cloud editor content with repository source of truth.

Problem: dbt Fusion deprecation in tests (dbt102).
- Symptom: accepted_values using old top-level values argument.
- Resolution: migrated syntax to accepted_values.arguments.values.

### 5.3 Analytics and BI

Problem: Power BI table visibility confusion.
- Symptom: expected marts not visible under assumed schema.
- Resolution: loaded from active dbt target schema in Snowflake and refreshed navigator.

Problem: Status distribution skewed to UNKNOWN.
- Symptom: low status-key match rate.
- Resolution: improved key normalization logic and remediated missing statuses in RAW source.

Problem: Slicer not affecting all KPIs consistently.
- Symptom: Rows In Range and High Rows In Range did not move with slicer.
- Resolution: used shared Dim_HOUR and relationships to both facts, corrected interaction settings.

Problem: KPI blanks and zeros.
- Symptom: High-risk cards showed blank or zero under filtered windows.
- Resolution: differentiated true zero from blank, updated measures with COALESCE, and validated sparse/mock data behavior.

## 6. Final Deliverables

Completed code and documents include:
- Ingestion services: src/api-server.ts, src/sensor-generator.ts
- Batch consumer: python/s3_consumer.py
- dbt models and tests: models/, tests/
- Phase analytics script: python/phase4_eda_template.py
- Orchestration/fallback assets: airflow/, scripts/phase3_manual_fallback.ps1
- Runbooks and summaries: docs/phase-*.md
- Final completion report: docs/project-completion-report.md

## 7. Completion Criteria and Verification

Completion criteria achieved:
- End-to-end movement from ingestion to analytics layer is operational.
- dbt marts and quality tests for core business models are present and validated.
- EDA artifacts are generated from Snowflake-backed data.
- Dashboard consumes transformed outputs and exposes operational KPIs.
- Project documentation now captures workflow, incidents, and decisions.

## 8. Remaining Limitations and Next Improvements

Current limitations:
- Mock/sparse timestamp data can flatten KPI movement under narrow filter windows.
- High-risk counts may remain zero when no HIGH rows exist in selected time range.
- Availability metric remains a proxy without full OEE quality/performance fields.

Recommended next steps:
1. Add richer MES/production quality fields for full OEE.
2. Expand simulated anomaly scenarios to stress risk model behavior.
3. Harden production deployment with secret rotation and scheduled validation jobs.
4. Add automated BI semantic tests for key DAX measures.

## 9. Project Close Statement

This project is complete as a portfolio-grade cloud data engineering and analytics solution. It demonstrates practical delivery under real constraints, clear fallback strategy design, and end-to-end ownership from ingestion through decision-support reporting.
