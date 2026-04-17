# Phase 4 Runbook (Business KPI, dbt Models, EDA, and Dashboard)

Date: 2026-04-17
Project: Cloud-Native Smart Factory Data Lakehouse

## Goal
Turn RAW factory data into business-facing metrics and a management dashboard.

## Data Inputs (already available)
- SMARTFACTORY_DB.RAW_DATA.SENSOR_DATA_RAW
- SMARTFACTORY_DB.RAW_DATA.MACHINE_STATUS_RAW
- SMARTFACTORY_DB.RAW_DATA.WORK_ORDERS_RAW

## Step 1 - Create dbt Deployment Environment (from current page)
Use this when you are on the dbt Cloud project page showing "Deployment environments".

1. Click "Create environment".
2. Set environment name to `prod`.
3. Environment type: `Deployment`.
4. Select your existing Snowflake connection.
5. Set execution credentials:
   - Database: `SMARTFACTORY_DB`
   - Warehouse: `COMPUTE_WH`
   - Role: `ACCOUNTADMIN` (for now; tighten later)
   - Schema: `ANALYTICS`
   - Threads: `4`
6. Click "Test connection" and make sure it passes.
7. Save.

Checkpoint:
- Environment appears in Deployment environments list.

## Step 2 - Build Phase 4 dbt models in Studio
Open Studio IDE and create these files.

### 2.1 Define RAW sources
Create `models/sources.yml`:

```yaml
version: 2

sources:
  - name: raw_data
    database: SMARTFACTORY_DB
    schema: RAW_DATA
    tables:
      - name: SENSOR_DATA_RAW
      - name: MACHINE_STATUS_RAW
      - name: WORK_ORDERS_RAW
```

### 2.2 Create staging models
Create `models/staging/stg_sensor_data.sql`:

```sql
select
    timestamp as event_ts,
    machine_id,
    temperature,
    vibration
from {{ source('raw_data', 'SENSOR_DATA_RAW') }}
where timestamp is not null
```

Create `models/staging/stg_machine_status.sql`:

```sql
select
    machine_id,
    status,
    last_updated as status_ts
from {{ source('raw_data', 'MACHINE_STATUS_RAW') }}
```

Create `models/staging/stg_work_orders.sql`:

```sql
select
    order_id,
    machine_id,
    product_name,
    target_quantity,
    order_status,
    created_at
from {{ source('raw_data', 'WORK_ORDERS_RAW') }}
```

Create `models/staging/staging_models.yml`:

```yaml
version: 2

models:
  - name: stg_sensor_data
    columns:
      - name: event_ts
        tests:
          - not_null
      - name: machine_id
        tests:
          - not_null
  - name: stg_machine_status
    columns:
      - name: machine_id
        tests:
          - not_null
      - name: status
        tests:
          - not_null
  - name: stg_work_orders
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      - name: machine_id
        tests:
          - not_null
```

### 2.3 Create marts models
Create `models/marts/fct_machine_health_hourly.sql`:

```sql
with sensor as (
    select
        date_trunc('hour', event_ts) as hour_ts,
        machine_id,
        avg(temperature) as avg_temperature,
        avg(vibration) as avg_vibration,
        sum(case when temperature > 90 or vibration > 2.0 then 1 else 0 end) as anomaly_events,
        count(*) as total_events
    from {{ ref('stg_sensor_data') }}
    group by 1, 2
),

latest_status as (
    select machine_id, status
    from (
        select
            machine_id,
            status,
            status_ts,
            row_number() over (partition by machine_id order by status_ts desc) as rn
        from {{ ref('stg_machine_status') }}
    ) t
    where rn = 1
)

select
    s.hour_ts,
    s.machine_id,
    s.avg_temperature,
    s.avg_vibration,
    s.anomaly_events,
    s.total_events,
    coalesce(ls.status, 'UNKNOWN') as current_status
from sensor s
left join latest_status ls using (machine_id)
```

Create `models/marts/fct_work_orders_status.sql`:

```sql
select
    date_trunc('day', created_at) as order_day,
    machine_id,
    order_status,
    count(*) as order_count,
    sum(target_quantity) as target_quantity_sum
from {{ ref('stg_work_orders') }}
group by 1, 2, 3
```

Create `models/marts/marts_models.yml`:

```yaml
version: 2

models:
  - name: fct_machine_health_hourly
    columns:
      - name: hour_ts
        tests:
          - not_null
      - name: machine_id
        tests:
          - not_null
  - name: fct_work_orders_status
    columns:
      - name: order_day
        tests:
          - not_null
      - name: machine_id
        tests:
          - not_null
```

Checkpoint:
- Files saved in Studio, no syntax errors shown.

## Step 3 - Execute dbt runs in order
Run these commands in dbt Cloud IDE command area:

1. `dbt deps`
2. `dbt build --select stg_sensor_data stg_machine_status stg_work_orders`
3. `dbt build --select fct_machine_health_hourly fct_work_orders_status`
4. `dbt test`

Expected:
- All models succeed.
- Tests pass.

If a model fails:
- Open run details.
- Fix SQL and rerun only failed model with `dbt run --select <model_name>`.

## Step 4 - Create first production job
1. Go to Deploy -> Jobs -> Create Job.
2. Job name: `phase4_hourly_kpi`.
3. Environment: `prod`.
4. Commands:
   - `dbt deps`
   - `dbt build --select fct_machine_health_hourly fct_work_orders_status`
5. Schedule: hourly.
6. Save and Run now.

Checkpoint:
- First successful job run with green status.

## Step 5 - Run EDA with Python
Use local script template `python/phase4_eda_template.py`.

Install packages:

```powershell
pip install -r python/requirements-phase4.txt
```

Set env vars (PowerShell example):

```powershell
$env:SNOWFLAKE_ACCOUNT = "<your_account_identifier>"
$env:SNOWFLAKE_USER = "<your_username>"
$env:SNOWFLAKE_PASSWORD = "<your_password>"
$env:SNOWFLAKE_ROLE = "ACCOUNTADMIN"
$env:SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
$env:SNOWFLAKE_DATABASE = "SMARTFACTORY_DB"
$env:SNOWFLAKE_SCHEMA = "RAW_DATA"
```

Run script:

```powershell
python python/phase4_eda_template.py
```

Output:
- Chart image under `artifacts/phase4/`
- Console summary for anomaly counts by machine

## Step 6 - Build Power BI dashboard (first version)
Connect Power BI to Snowflake and import these tables/views:
- ANALYTICS.FCT_MACHINE_HEALTH_HOURLY
- ANALYTICS.FCT_WORK_ORDERS_STATUS
- RAW_DATA.MACHINE_STATUS_RAW (optional for quick cards)

Suggested visuals:
1. Real-time Health
   - Card: latest avg_temperature
   - Card: latest anomaly_events
2. Time-series Trend
   - Line chart: hour_ts vs avg_temperature and avg_vibration
3. Operations View
   - Donut chart: current_status distribution
4. Work Orders
   - Stacked bar: order_status by machine_id

## Step 7 - Interview-ready business narrative
Use this concise story:
- Built ingestion from IoT and MES sources into Snowflake RAW.
- Modeled business-facing KPIs with dbt marts.
- Produced anomaly and machine-health insights for maintenance decisions.
- Delivered a dashboard for plant-level monitoring and action.

## Known limitation and roadmap
Current data supports OEE proxy, not full OEE:
- Availability: can estimate from RUNNING vs non-RUNNING status patterns.
- Performance: can estimate from work order progress.
- Quality: needs good_count/reject_count fields for true quality ratio.

Recommended next enhancement:
- Add produced_qty, good_qty, reject_qty, planned_runtime_minutes, and downtime_reason in MES pipeline.
