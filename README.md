# Cloud-Native-Smart-Factory-Data-Lakehouse

## Project Checkpoint

- Phase 2 status snapshot (2026-04-16): `docs/phase-2-checkpoint-2026-04-16.md`

## Phase 3 Starter Kit

- Runbook: `docs/phase-3-runbook.md`
- Snowflake Step 1 SQL: `sql/snowflake/phase3_step1_create_mes_raw_tables.sql`
- Snowflake Step 2 SQL template: `sql/snowflake/phase3_step2_storage_integration_template.sql`
- Snowflake Step 5 validation SQL: `sql/snowflake/phase3_step5_validation_queries.sql`
- Airflow DAG: `airflow/dags/smartfactory_phase3_ingestion.py`
- Airflow local runtime compose: `airflow/docker-compose.local.yml`
- Manual fallback (no Airflow runtime): `scripts/phase3_manual_fallback.ps1`
- PostgreSQL MES source setup: `sql/postgres/phase3_prepare_mes_source_tables.sql`

## Sensor Data Generator (Direct to RabbitMQ)

This project includes a TypeScript sensor data generator that continuously publishes machine telemetry to RabbitMQ.

### Payload format

The generator publishes JSON payloads like:

{
	"timestamp": "2026-04-14T07:30:00Z",
	"machine_id": "M-001",
	"temperature": 85.5,
	"vibration": 1.2
}

### Setup

1. Start RabbitMQ and Postgres with Docker Compose.
2. Install dependencies.
3. Run the generator.

Commands:

docker compose up -d
npm install
npm run dev

### Config via environment variables

- RABBITMQ_URL (default: amqp://guest:guest@localhost:5672)
- RABBITMQ_QUEUE (default: sensor_data_queue)
- PUBLISH_INTERVAL_MS (default: 1000)
- MACHINE_IDS (default: M-001,M-002,M-003)

## Sensor Ingestion API + UI Dashboard

This API receives sensor payloads over HTTP, publishes them to RabbitMQ, and exposes a simple dashboard UI.

### Run API server

docker compose up -d
npm install
npm run dev:api

### Open dashboard

http://localhost:3000

### API endpoint

POST /api/sensor-data

Example JSON:

{
	"timestamp": "2026-04-14T07:30:00Z",
	"machine_id": "M-001",
	"temperature": 85.5,
	"vibration": 1.2
}

## Load Test with k6

The k6 script sends sensor data to the API and simulates 1,000 machines for 1 minute.

Script:

k6/sensor-load-test.js

Run command:

k6 run k6/sensor-load-test.js

Optional custom API base URL:

k6 run -e BASE_URL=http://localhost:3000 k6/sensor-load-test.js

## Data Ingestion Consumer (RabbitMQ to AWS S3)

This Python consumer reads messages from sensor_data_queue, batches records in memory, then writes a batch file and uploads it to S3.

Batch flush conditions (whichever comes first):

- 10,000 messages
- 5 minutes (300 seconds)

### Files

- python/s3_consumer.py
- python/requirements.txt

### Install dependencies

pip install -r python/requirements.txt

### Required environment variables

- S3_BUCKET: target S3 bucket name

### Optional environment variables

- RABBITMQ_URL (default: amqp://guest:guest@localhost:5672)
- RABBITMQ_QUEUE (default: sensor_data_queue)
- BATCH_SIZE (default: 10000)
- FLUSH_INTERVAL_SECONDS (default: 300)
- OUTPUT_FORMAT (default: json, allowed: json or csv)
- S3_PREFIX (default: sensor-data)

### Run consumer

python python/s3_consumer.py

### S3 object layout

Uploaded files are partitioned by date:

S3_PREFIX/year=YYYY/month=MM/day=DD/sensor_data_YYYYMMDD_HHMMSS.json

or

S3_PREFIX/year=YYYY/month=MM/day=DD/sensor_data_YYYYMMDD_HHMMSS.csv
