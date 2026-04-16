from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.transfers.sql_to_s3 import SqlToS3Operator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

SNOWFLAKE_DATABASE = "SMARTFACTORY_DB"
SNOWFLAKE_SCHEMA = "RAW_DATA"
SNOWFLAKE_STAGE = "MY_SECURE_S3_STAGE"

S3_BUCKET = Variable.get("smartfactory_s3_bucket", default_var="replace-me")
SENSOR_S3_PREFIX = Variable.get("sensor_s3_prefix", default_var="sensor-data")
MES_S3_PREFIX = Variable.get("mes_s3_prefix", default_var="mes-data")

with DAG(
    dag_id="smartfactory_phase3_ingestion",
    description="Hourly ingestion from S3/Postgres into Snowflake RAW layer",
    start_date=datetime(2026, 4, 16),
    schedule_interval="@hourly",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-engineering",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["smartfactory", "phase3", "snowflake", "airflow"],
) as dag:
    load_sensor_to_snowflake = SnowflakeOperator(
        task_id="load_sensor_data",
        snowflake_conn_id="snowflake_conn",
        sql=f"""
        COPY INTO {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.SENSOR_DATA_RAW
          (TIMESTAMP, MACHINE_ID, TEMPERATURE, VIBRATION)
        FROM (
          SELECT
            TRY_TO_TIMESTAMP_NTZ($1:timestamp::STRING),
            $1:machine_id::STRING,
            TRY_TO_DOUBLE($1:temperature::STRING),
            TRY_TO_DOUBLE($1:vibration::STRING)
          FROM @{SNOWFLAKE_STAGE}
        )
        FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = TRUE)
        PATTERN = '.*{SENSOR_S3_PREFIX}/year=.*/month=.*/day=.*/.*\\.json'
        ON_ERROR = 'CONTINUE';
        """,
    )

    extract_work_orders_to_s3 = SqlToS3Operator(
        task_id="extract_work_orders_to_s3",
        sql_conn_id="postgres_conn",
        aws_conn_id="aws_conn",
        query="""
            SELECT
                order_id,
                machine_id,
                product_name,
                target_quantity,
                order_status,
                created_at
            FROM work_orders;
        """,
        s3_bucket=S3_BUCKET,
        s3_key=f"{MES_S3_PREFIX}/work_orders/work_orders_{{{{ ds_nodash }}}}.csv",
        replace=True,
        file_format="csv",
        pd_kwargs={"index": False},
    )

    load_work_orders_to_snowflake = SnowflakeOperator(
        task_id="load_work_orders_to_snowflake",
        snowflake_conn_id="snowflake_conn",
        sql=f"""
        COPY INTO {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.WORK_ORDERS_RAW
          (ORDER_ID, MACHINE_ID, PRODUCT_NAME, TARGET_QUANTITY, ORDER_STATUS, CREATED_AT)
        FROM (
          SELECT
            $1::STRING,
            $2::STRING,
            $3::STRING,
            TRY_TO_NUMBER($4::STRING),
            $5::STRING,
            TRY_TO_TIMESTAMP_NTZ($6::STRING)
          FROM @{SNOWFLAKE_STAGE}/{MES_S3_PREFIX}/work_orders
        )
        FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
        PATTERN = '.*work_orders_.*\\.csv'
        ON_ERROR = 'CONTINUE';
        """,
    )

    extract_machine_status_to_s3 = SqlToS3Operator(
        task_id="extract_machine_status_to_s3",
        sql_conn_id="postgres_conn",
        aws_conn_id="aws_conn",
        query="""
            SELECT
                machine_id,
                status,
                last_updated
            FROM machine_status;
        """,
        s3_bucket=S3_BUCKET,
        s3_key=f"{MES_S3_PREFIX}/machine_status/machine_status_{{{{ ds_nodash }}}}.csv",
        replace=True,
        file_format="csv",
        pd_kwargs={"index": False},
    )

    load_machine_status_to_snowflake = SnowflakeOperator(
        task_id="load_machine_status_to_snowflake",
        snowflake_conn_id="snowflake_conn",
        sql=f"""
        COPY INTO {SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.MACHINE_STATUS_RAW
          (MACHINE_ID, STATUS, LAST_UPDATED)
        FROM (
          SELECT
            $1::STRING,
            $2::STRING,
            TRY_TO_TIMESTAMP_NTZ($3::STRING)
          FROM @{SNOWFLAKE_STAGE}/{MES_S3_PREFIX}/machine_status
        )
        FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
        PATTERN = '.*machine_status_.*\\.csv'
        ON_ERROR = 'CONTINUE';
        """,
    )

    extract_work_orders_to_s3 >> load_work_orders_to_snowflake
    extract_machine_status_to_s3 >> load_machine_status_to_snowflake
    [load_work_orders_to_snowflake, load_machine_status_to_snowflake] >> load_sensor_to_snowflake
