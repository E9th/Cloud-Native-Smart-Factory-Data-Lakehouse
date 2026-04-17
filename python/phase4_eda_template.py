import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import snowflake.connector


TEMP_THRESHOLD = 90.0
VIB_THRESHOLD = 2.0


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=required_env("SNOWFLAKE_ACCOUNT"),
        user=required_env("SNOWFLAKE_USER"),
        password=required_env("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "SMARTFACTORY_DB"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW_DATA"),
    )


def load_sensor_data(conn: snowflake.connector.SnowflakeConnection) -> pd.DataFrame:
    query = """
        SELECT
            TIMESTAMP,
            MACHINE_ID,
            TEMPERATURE,
            VIBRATION
        FROM SMARTFACTORY_DB.RAW_DATA.SENSOR_DATA_RAW
        WHERE TIMESTAMP >= DATEADD('day', -3, CURRENT_TIMESTAMP())
        ORDER BY TIMESTAMP
    """
    return pd.read_sql(query, conn)


def save_temperature_trend(df: pd.DataFrame, machine_id: str, out_dir: Path) -> Path:
    machine_df = df[df["MACHINE_ID"] == machine_id].copy()
    if machine_df.empty:
        raise RuntimeError(f"No data found for machine_id={machine_id}")

    plt.figure(figsize=(12, 5))
    sns.lineplot(data=machine_df, x="TIMESTAMP", y="TEMPERATURE", linewidth=1.2)
    plt.title(f"Temperature Trend - {machine_id}")
    plt.axhline(y=TEMP_THRESHOLD, color="red", linestyle="--", label="Warning threshold")
    plt.xlabel("Timestamp")
    plt.ylabel("Temperature")
    plt.legend()
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"temperature_trend_{machine_id}.png"
    plt.savefig(out_path, dpi=140)
    plt.close()
    return out_path


def print_anomaly_summary(df: pd.DataFrame) -> None:
    anomaly_df = df[(df["TEMPERATURE"] > TEMP_THRESHOLD) | (df["VIBRATION"] > VIB_THRESHOLD)].copy()
    summary = (
        anomaly_df.groupby("MACHINE_ID", dropna=False)
        .size()
        .reset_index(name="anomaly_count")
        .sort_values("anomaly_count", ascending=False)
    )

    total_rows = len(df)
    anomaly_rows = len(anomaly_df)
    pct = (anomaly_rows / total_rows * 100.0) if total_rows else 0.0

    print("=== Phase 4 EDA Summary ===")
    print(f"Total rows: {total_rows}")
    print(f"Anomaly rows: {anomaly_rows} ({pct:.2f}%)")
    print("Anomaly count by machine:")

    if summary.empty:
        print("No anomalies found by current thresholds.")
    else:
        print(summary.to_string(index=False))


def main() -> None:
    sns.set_theme(style="whitegrid")

    conn = get_connection()
    try:
        df = load_sensor_data(conn)
    finally:
        conn.close()

    if df.empty:
        raise RuntimeError("SENSOR_DATA_RAW returned no rows for the last 3 days.")

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])

    out_file = save_temperature_trend(df, machine_id="M-001", out_dir=Path("artifacts") / "phase4")
    print_anomaly_summary(df)
    print(f"Saved chart: {out_file}")


if __name__ == "__main__":
    main()
