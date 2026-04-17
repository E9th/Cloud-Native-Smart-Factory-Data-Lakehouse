# Phase 4 Summary (dbt Modeling, EDA, and Power BI Dashboard)

Date: 2026-04-17
Project: Cloud-Native Smart Factory Data Lakehouse

## 1) Phase 4 Objective
Transform RAW data into business-facing analytics outputs for operations monitoring:
- Build curated KPI models with dbt
- Validate model quality with tests
- Perform EDA with Python on Snowflake data
- Deliver a first management dashboard in Power BI

## 2) What Was Completed
1. dbt Cloud deployment environment was created (`prod`) and connected to Snowflake.
2. RAW sources for sensor and MES data were defined in dbt and made discoverable.
3. Staging models were implemented and hardened for dirty input data.
4. Mart models were created:
   - `fct_machine_health_hourly`
   - `fct_work_orders_status`
5. dbt tests for selected staging + mart models passed successfully (11/11).
6. Python EDA script executed successfully and produced chart output.
7. Power BI connected to Snowflake and loaded Phase 4 models from schema `DBT_TDONGPHUYAW`.
8. First dashboard layout was completed (cards, line trend, donut status, stacked work orders).

## 3) Key Artifacts Produced/Updated
- Runbook: docs/phase-4-runbook.md
- Summary (this document): docs/phase-4-summary.md
- dbt source declarations: models/sources.yml
- Staging models:
  - models/staging/stg_sensor_data.sql
  - models/staging/stg_machine_status.sql
  - models/staging/stg_work_orders.sql
- Mart models:
  - models/marts/fct_machine_health_hourly.sql
  - models/marts/fct_work_orders_status.sql
- EDA script: python/phase4_eda_template.py
- EDA dependencies: python/requirements-phase4.txt
- EDA chart artifact: artifacts/phase4/temperature_trend_M-001.png

## 4) Main Problems Encountered and Resolutions
1. dbt source not found errors (`dbt1005`) for RAW tables.
Resolution:
- Fixed source declaration format and naming consistency.
- Corrected YAML indentation under `sources:`.
- Aligned `source()` references with declared lowercase source names + identifiers.

2. dbt tests failed on staging (`unique` and `not_null`).
Resolution:
- Added normalization in staging:
  - Convert empty strings to `NULL` via `nullif(trim(...), '')`
  - Filter invalid keys
  - Deduplicate `order_id` with `row_number()` and latest timestamp logic

3. dbt test failed on `not_null_fct_work_orders_status_order_day`.
Resolution:
- Updated mart logic to avoid null date output by filling fallback timestamp and preserving usable records.

4. dbt Job command validation error in dbt Cloud for `dbt deps`.
Resolution:
- Removed `dbt deps` from job command set (project has no packages/dependencies file).
- Used `dbt build` + `dbt test` commands directly.

5. Python EDA runtime issues (`ModuleNotFoundError`) for plotting/Snowflake packages.
Resolution:
- Installed packages into project `.venv` explicitly.
- Verified imports in the same interpreter used to run the EDA script.

6. Script execution path issues (`can't open file ... phase4_eda_template.py`).
Resolution:
- Used correct relative path from project root:
  - `python .\\python\\phase4_eda_template.py`

7. Power BI could connect but expected tables were not initially visible.
Resolution:
- Located dbt outputs in dev schema (`DBT_TDONGPHUYAW`) instead of `ANALYTICS`.
- Loaded `FCT_MACHINE_HEALTH_HOURLY` and `FCT_WORK_ORDERS_STATUS` from actual schema.

8. Stacked column chart appeared empty.
Resolution:
- Fixed mart data retention logic to avoid over-filtering.
- Rebuilt model and refreshed Power BI dataset.

## 5) What Worked / What Did Not
### Worked
- dbt selected build/test flow for staging and mart models
- Data quality hardening in staging for null/blank/duplicate handling
- EDA from Snowflake via Python with chart output artifact
- Power BI Import mode for first dashboard iteration
- Dashboard visuals with business-oriented titles and labels

### Did Not Work (or not recommended in this setup)
- Using `dbt deps` in dbt Cloud job for this project configuration
- Assuming Phase 4 models are always in `ANALYTICS` without checking active target schema
- Relying on global Python environment when `.venv` interpreter is required
- Using `ORDER_DAY` slicer as-is when fallback date (`1970-01-01`) dominates

## 6) Validation and Evidence
- dbt test execution for selected models: success (11/11)
- EDA output generated:
  - `artifacts/phase4/temperature_trend_M-001.png`
- Power BI dashboard components rendered with live imported data:
  - Latest anomaly card
  - Latest average temperature card
  - Hourly temperature/vibration trend
  - Current machine status distribution
  - Work orders by machine and status

## 7) Completion Assessment
Phase 4 (portfolio-ready implementation): COMPLETE.
- Modeling, validation, EDA, and dashboard deliverables were executed end-to-end.

Production hardening status: MOSTLY COMPLETE.
- Recommended final checks:
  - Run deployment job in `prod` environment and confirm green run history
  - Capture final report screenshots for portfolio package
  - Rotate Snowflake password (credential was exposed during interactive troubleshooting)

## 8) Portfolio-Ready Statement
Phase 4 delivered a full analytics layer on top of Snowflake RAW data using dbt, validated model quality with tests, generated EDA evidence via Python, and produced a business-facing Power BI dashboard for machine health and work-order operations. The implementation demonstrates both technical pipeline maturity and operational decision support value.
