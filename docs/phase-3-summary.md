# Phase 3 Summary (Airflow Orchestration and Fallback)

Date: 2026-04-16
Project: Cloud-Native Smart Factory Data Lakehouse

## 1) Phase 3 Objective
Build an automated data bridge to load both streams into Snowflake RAW layer:
- Sensor data: S3 -> Snowflake
- MES data: PostgreSQL -> S3 -> Snowflake
- Orchestration target: Apache Airflow

## 2) What Was Completed
1. Snowflake RAW setup for MES tables was completed.
2. Secure S3 bridge via Snowflake Storage Integration and External Stage was completed.
3. PostgreSQL source tables were prepared and seeded.
4. MES extraction and S3 upload path was executed successfully.
5. Snowflake COPY load path for MES was generated and executed through fallback flow.
6. Step 5 validation SQL was executed in Snowflake worksheet.

## 3) Key Artifacts Produced/Updated
- Runbook: docs/phase-3-runbook.md
- Summary (this document): docs/phase-3-summary.md
- Airflow local compose: airflow/docker-compose.local.yml
- Airflow DAG: airflow/dags/smartfactory_phase3_ingestion.py
- Postgres prep SQL: sql/postgres/phase3_prepare_mes_source_tables.sql
- Snowflake validation SQL: sql/snowflake/phase3_step5_validation_queries.sql
- Manual fallback script: scripts/phase3_manual_fallback.ps1

## 4) Main Problems Encountered and Resolutions
1. Snowflake AssumeRole failures due to trust-policy mismatch.
Resolution: aligned AWS IAM trust policy with Snowflake integration values from DESC STORAGE INTEGRATION, including updated external id after integration recreation.

2. AccessDenied on stage listing and object reads.
Resolution: corrected IAM role permissions to include S3 ListBucket and GetObject on target bucket/prefix.

3. Running PostgreSQL SQL in Snowflake by mistake (Unknown function NOW).
Resolution: clarified engine boundaries in SQL/runbook and re-ran Postgres script in PostgreSQL container.

4. Airflow runtime bootstrap blocked by Docker image pull EOF/network issues.
Resolution: attempted multiple tags and registries; when still blocked, implemented manual fallback path to keep Phase 3 moving.

5. AWS credentials issue on default profile (NoCredentials).
Resolution: used verified working profile smartfactory and exported AWS_PROFILE before running fallback flow.

6. Manual script invocation produced no output when called without explicit path.
Resolution: invoked script with explicit path and call operator:
- & .\scripts\phase3_manual_fallback.ps1 -BucketName <bucket>

7. PowerShell interpolation bug in generated Snowflake SQL ($1, $2, ...).
Resolution: changed SQL template handling in scripts/phase3_manual_fallback.ps1 to preserve Snowflake positional columns literally and replace only stage/prefix placeholders.

## 5) Fallback Execution Result (Verified)
Manual fallback completed successfully:
- Exported work_orders and machine_status from PostgreSQL container
- Uploaded CSV files to S3 bucket under mes-data/work_orders and mes-data/machine_status
- Printed runnable Snowflake COPY SQL

Example successful uploads:
- s3://smartfactory-datalake-dev-319627300527-us-east-1-an/mes-data/work_orders/work_orders_20260416_205410.csv
- s3://smartfactory-datalake-dev-319627300527-us-east-1-an/mes-data/machine_status/machine_status_20260416_205410.csv

## 6) Validation Status
Step 5 validation SQL was run in Snowflake worksheet and returned result sets for RAW tables.

Validation script:
- sql/snowflake/phase3_step5_validation_queries.sql

## 7) Completion Assessment
Functional completion for Phase 3 data movement: COMPLETE.
- Data paths and loads to Snowflake RAW are working.
- Validation queries run successfully.

Strict Airflow-orchestrator completion (DAG run proof): PARTIALLY COMPLETE.
- DAG definition and local runtime assets exist.
- Local Airflow container startup was blocked by external image pull/network constraint, so fallback execution was used.

## 8) Portfolio-Ready Statement
Phase 3 delivered a production-style secure ingestion bridge (Storage Integration + stage-based loading) and a resilient fallback execution strategy that kept delivery on schedule despite runtime infrastructure constraints. The pipeline reliably moved MES and sensor-aligned data into Snowflake RAW and validated readiness for downstream transformation in Phase 4.
