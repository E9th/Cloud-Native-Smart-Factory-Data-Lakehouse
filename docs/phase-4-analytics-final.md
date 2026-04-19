# Phase 4 Final Analytics Pack

Date: 2026-04-18
Project: Cloud-Native Smart Factory Data Lakehouse

## Goal
Deliver the final analytics layer that is interview-ready for a Junior Data Engineer and Analytics role.

This pack adds:
- Feature engineering for predictive-maintenance style analytics
- Machine risk scoring and ranking
- Baseline-driven anomaly rules by machine
- Dashboard actions that are tied to business decisions

## New/Updated Artifacts
- New dbt mart: models/marts/fct_machine_risk_hourly.sql
- Updated marts tests: models/marts/marts_models.yml
- New test: tests/fct_machine_risk_hourly_risk_score_range.sql
- Upgraded EDA script: python/phase4_eda_template.py

## Step 1 - Build analytics mart in dbt
Run in dbt Cloud IDE or local dbt CLI:

```bash
dbt build --select fct_machine_health_hourly fct_machine_risk_hourly
dbt test --select fct_machine_risk_hourly
```

Expected output columns from fct_machine_risk_hourly:
- rolling_mean_temp_3h
- rolling_std_temp_3h
- rolling_mean_vibration_3h
- rolling_std_vibration_3h
- temp_rate_of_change
- vibration_rate_of_change
- anomaly_rate_3h
- temp_threshold_baseline
- vibration_threshold_baseline
- machine_risk_score
- machine_risk_level (LOW, MEDIUM, HIGH)

## Step 2 - Run Python analytics script
Install dependencies in project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\python\requirements-phase4.txt
```

Set Snowflake credentials (PowerShell):

```powershell
$env:SNOWFLAKE_ACCOUNT = "<your_account>"
$env:SNOWFLAKE_USER = "<your_user>"
$env:SNOWFLAKE_PASSWORD = "<your_password>"
$env:SNOWFLAKE_ROLE = "ACCOUNTADMIN"
$env:SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
$env:SNOWFLAKE_DATABASE = "SMARTFACTORY_DB"
$env:SNOWFLAKE_SCHEMA = "RAW_DATA"
```

Run:

```powershell
.\.venv\Scripts\python.exe .\python\phase4_eda_template.py
```

Generated outputs under artifacts/phase4:
- correlation_heatmap.png
- temperature_vs_vibration_scatter.png
- temperature_threshold_trend_<machine_id>.png
- machine_baseline_summary.csv
- sustained_temp_breach_events.csv
- machine_risk_ranking.csv

## Step 3 - Power BI advanced dashboard updates
Import one additional table:
- DBT_TDONGPHUYAW.FCT_MACHINE_RISK_HOURLY

Create these DAX measures:

```DAX
Availability Proxy % =
DIVIDE(
    CALCULATE(
        COUNTROWS(FCT_MACHINE_HEALTH_HOURLY),
        FCT_MACHINE_HEALTH_HOURLY[CURRENT_STATUS] = "RUNNING"
    ),
    COUNTROWS(FCT_MACHINE_HEALTH_HOURLY)
) * 100
```

```DAX
High Risk Machines =
CALCULATE(
    DISTINCTCOUNT(FCT_MACHINE_RISK_HOURLY[MACHINE_ID]),
    FCT_MACHINE_RISK_HOURLY[MACHINE_RISK_LEVEL] = "HIGH"
)
```

```DAX
Avg Machine Risk Score =
AVERAGE(FCT_MACHINE_RISK_HOURLY[MACHINE_RISK_SCORE])
```

Recommended visuals:
1. Card: Availability Proxy %
2. Card: High Risk Machines
3. Bar chart: machine_id vs machine_risk_score (descending)
4. Line chart: hour_ts vs avg_temperature, with Analytics pane constant line at 85 (or per-machine baseline from machine_baseline_summary.csv)
5. Table: machine_id, machine_risk_level, temp_threshold_breach, vibration_threshold_breach

## Step 4 - Interview "So What" storyline
Use this structure in README, portfolio PDF, or interview talk:

1. Problem
- Factory has unplanned downtime risk from sudden machine behavior shifts.

2. Solution
- Built cloud-native ingestion and transformation pipeline, then added analytics features and risk scoring.

3. Business impact
- Identified which machines have the highest operational risk first.
- Added baseline rules and threshold visuals so operations can act before severe failure.
- Delivered an actionable dashboard that supports shift-level maintenance prioritization.

## Guardrails for honest portfolio claims
- Report current output as risk scoring and early warning, not final ML prediction.
- Call OEE metric an availability proxy unless full quality/performance fields exist.
- Keep a short "limitations" section in README to show engineering maturity.
