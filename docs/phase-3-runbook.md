# Phase 3 Runbook (Airflow Orchestration)

This runbook starts Phase 3 in four practical steps and maps each step to files in this repository.

## Goal
Build an orchestrated pipeline with Airflow to move:
- Sensor data: S3 -> Snowflake
- MES data: PostgreSQL -> S3 -> Snowflake

## Step 1: Prepare Snowflake raw tables for MES
Run:
- sql/snowflake/phase3_step1_create_mes_raw_tables.sql

Expected result:
- SMARTFACTORY_DB.RAW_DATA.MACHINE_STATUS_RAW exists
- SMARTFACTORY_DB.RAW_DATA.WORK_ORDERS_RAW exists

## Step 2: Create secure S3 bridge with Storage Integration
Run and replace placeholders:
- sql/snowflake/phase3_step2_storage_integration_template.sql

Notes:
- Use ACCOUNTADMIN role.
- After `DESC STORAGE INTEGRATION S3_INT`, copy Snowflake IAM user/external id into AWS role trust policy.
- Validate with `LIST @MY_SECURE_S3_STAGE`.

## Step 3: Set up Airflow connections and variables
DAG file:
- airflow/dags/smartfactory_phase3_ingestion.py

If you do not already have an Airflow runtime, start local Airflow first:
- airflow/docker-compose.local.yml

Start commands:
```powershell
docker compose -f airflow/docker-compose.local.yml up -d airflow-db airflow-init
docker compose -f airflow/docker-compose.local.yml up -d airflow-webserver airflow-scheduler
```

Open Airflow UI:
- http://localhost:8080
- Username: admin
- Password: admin

Create these Airflow connections in UI (Admin -> Connections):
- snowflake_conn
- postgres_conn
- aws_conn

Set Airflow Variables (Admin -> Variables):
- smartfactory_s3_bucket = your bucket name
- sensor_s3_prefix = sensor-data
- mes_s3_prefix = mes-data

### Fallback when Airflow image pull is blocked
If Docker image pulls fail repeatedly (for example EOF while pulling `apache/airflow`), use this fallback to continue Phase 3:

- scripts/phase3_manual_fallback.ps1

What it does:
- Export `work_orders` and `machine_status` from PostgreSQL container into CSV
- Upload both CSV files to S3 under `mes-data/...`
- Print ready-to-run Snowflake `COPY INTO` SQL

Example:
```powershell
./scripts/phase3_manual_fallback.ps1 -BucketName <your-bucket-name>
```

Prerequisites for fallback:
- `docker` command works and `postgres` container is running
- AWS CLI credentials are configured (`aws configure`)

## Step 4: Enable Postgres -> S3 -> Snowflake path
Prepare source tables in Postgres:
- sql/postgres/phase3_prepare_mes_source_tables.sql

Example command (host):
```powershell
psql -h localhost -p 5433 -U smartfactory_user -d smartfactory_db -f sql/postgres/phase3_prepare_mes_source_tables.sql
```

DAG flow:
1. extract_work_orders_to_s3
2. load_work_orders_to_snowflake
3. extract_machine_status_to_s3
4. load_machine_status_to_snowflake
5. load_sensor_data

## Step 5: Validate end-to-end pipeline result in Snowflake
Run:
- sql/snowflake/phase3_step5_validation_queries.sql

Phase 3 is considered complete when:
- `LIST @MY_SECURE_S3_STAGE` works without auth errors
- Airflow DAG run succeeds end-to-end
- RAW table row counts increase and latest timestamps are recent

## Validation Checklist
- Airflow DAG `smartfactory_phase3_ingestion` appears and is ON.
- Manual trigger succeeds.
- Snowflake row counts increase in:
  - RAW_DATA.WORK_ORDERS_RAW
  - RAW_DATA.MACHINE_STATUS_RAW
  - RAW_DATA.SENSOR_DATA_RAW

Manual trigger options:
```powershell
docker exec -it airflow-webserver airflow dags unpause smartfactory_phase3_ingestion
docker exec -it airflow-webserver airflow dags trigger smartfactory_phase3_ingestion
docker exec -it airflow-webserver airflow dags state smartfactory_phase3_ingestion "$(Get-Date -Format yyyy-MM-ddTHH:mm:ss)"
```

## Troubleshooting
- `AccessDenied` on stage: verify IAM role trust policy and allowed bucket path.
- Empty MES loads: verify Postgres source tables contain rows.
- CSV parse issues: ensure Snowflake copy uses skip header and quote options.
- `Unknown function NOW` in Snowflake: you likely ran `sql/postgres/phase3_prepare_mes_source_tables.sql` in Snowflake by mistake. Run that script in PostgreSQL only.
- `NoCredentials` from AWS CLI: run `aws configure` and retry the fallback script.
- `EOF` while pulling Airflow image: use fallback script and proceed with manual Snowflake copy + Step 5 validation.
