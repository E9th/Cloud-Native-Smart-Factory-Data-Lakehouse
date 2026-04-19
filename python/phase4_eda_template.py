import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import snowflake.connector


MIN_TEMP_BASELINE = 85.0
MIN_VIB_BASELINE = 2.0
LOOKBACK_DAYS = 7
ROLLING_WINDOW_HOURS = 3
MIN_SUSTAINED_BREACH_MINUTES = 15


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
        WHERE TIMESTAMP >= DATEADD('day', -7, CURRENT_TIMESTAMP())
        ORDER BY TIMESTAMP
    """
    return pd.read_sql(query, conn)


def enrich_sensor_data(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["TIMESTAMP"] = pd.to_datetime(enriched["TIMESTAMP"])
    enriched["MACHINE_ID"] = enriched["MACHINE_ID"].astype(str).str.strip().str.upper()
    enriched["ANOMALY_FLAG"] = (
        (enriched["TEMPERATURE"] > MIN_TEMP_BASELINE)
        | (enriched["VIBRATION"] > MIN_VIB_BASELINE)
    ).astype(int)
    return enriched


def build_hourly_features(df: pd.DataFrame) -> pd.DataFrame:
    hourly = (
        df.set_index("TIMESTAMP")
        .groupby("MACHINE_ID")
        .resample("1h")
        .agg(
            AVG_TEMPERATURE=("TEMPERATURE", "mean"),
            AVG_VIBRATION=("VIBRATION", "mean"),
            ANOMALY_EVENTS=("ANOMALY_FLAG", "sum"),
            TOTAL_EVENTS=("ANOMALY_FLAG", "count"),
        )
        .reset_index()
    )

    hourly["ANOMALY_FLAG_RATE"] = hourly["ANOMALY_EVENTS"] / hourly["TOTAL_EVENTS"].where(
        hourly["TOTAL_EVENTS"] != 0,
        pd.NA,
    )
    hourly["ANOMALY_FLAG_RATE"] = hourly["ANOMALY_FLAG_RATE"].fillna(0.0)

    hourly = hourly.sort_values(["MACHINE_ID", "TIMESTAMP"]).copy()
    grouped = hourly.groupby("MACHINE_ID", group_keys=False)

    hourly["ROLLING_MEAN_TEMP_3H"] = grouped["AVG_TEMPERATURE"].transform(
        lambda s: s.rolling(ROLLING_WINDOW_HOURS, min_periods=1).mean()
    )
    hourly["ROLLING_STD_TEMP_3H"] = grouped["AVG_TEMPERATURE"].transform(
        lambda s: s.rolling(ROLLING_WINDOW_HOURS, min_periods=1).std().fillna(0.0)
    )
    hourly["ROLLING_MEAN_VIB_3H"] = grouped["AVG_VIBRATION"].transform(
        lambda s: s.rolling(ROLLING_WINDOW_HOURS, min_periods=1).mean()
    )
    hourly["ROLLING_STD_VIB_3H"] = grouped["AVG_VIBRATION"].transform(
        lambda s: s.rolling(ROLLING_WINDOW_HOURS, min_periods=1).std().fillna(0.0)
    )
    hourly["TEMP_RATE_OF_CHANGE"] = grouped["AVG_TEMPERATURE"].transform(lambda s: s.diff().fillna(0.0))
    hourly["VIB_RATE_OF_CHANGE"] = grouped["AVG_VIBRATION"].transform(lambda s: s.diff().fillna(0.0))

    return hourly


def correlation_analysis(hourly: pd.DataFrame, out_dir: Path) -> float:
    corr_cols = ["AVG_TEMPERATURE", "AVG_VIBRATION", "ANOMALY_FLAG_RATE"]
    corr_matrix = hourly[corr_cols].corr(method="pearson")

    plt.figure(figsize=(7, 5))
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="YlOrRd", vmin=-1, vmax=1)
    plt.title("Correlation Matrix (Hourly Features)")
    plt.tight_layout()
    plt.savefig(out_dir / "correlation_heatmap.png", dpi=140)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.scatterplot(
        data=hourly,
        x="AVG_TEMPERATURE",
        y="AVG_VIBRATION",
        hue="ANOMALY_FLAG_RATE",
        palette="rocket",
        alpha=0.75,
        s=40,
    )
    plt.title("Temperature vs Vibration (Colored by Anomaly Rate)")
    plt.tight_layout()
    plt.savefig(out_dir / "temperature_vs_vibration_scatter.png", dpi=140)
    plt.close()

    return float(corr_matrix.loc["AVG_TEMPERATURE", "AVG_VIBRATION"])


def compute_machine_baselines(hourly: pd.DataFrame) -> pd.DataFrame:
    baseline = (
        hourly.groupby("MACHINE_ID", as_index=False)
        .agg(
            MACHINE_TEMP_P95=("AVG_TEMPERATURE", lambda s: s.quantile(0.95)),
            MACHINE_VIB_P95=("AVG_VIBRATION", lambda s: s.quantile(0.95)),
        )
    )
    baseline["TEMP_THRESHOLD_BASELINE"] = baseline["MACHINE_TEMP_P95"].clip(lower=MIN_TEMP_BASELINE)
    baseline["VIB_THRESHOLD_BASELINE"] = baseline["MACHINE_VIB_P95"].clip(lower=MIN_VIB_BASELINE)
    return baseline


def detect_sustained_temperature_breaches(
    df: pd.DataFrame,
    baselines: pd.DataFrame,
    min_duration_minutes: int = MIN_SUSTAINED_BREACH_MINUTES,
) -> pd.DataFrame:
    threshold_map = dict(zip(baselines["MACHINE_ID"], baselines["TEMP_THRESHOLD_BASELINE"]))
    events = []

    for machine_id, machine_df in df.sort_values("TIMESTAMP").groupby("MACHINE_ID"):
        threshold = threshold_map.get(machine_id, MIN_TEMP_BASELINE)
        machine_df = machine_df.copy()
        machine_df["TEMP_BREACH"] = machine_df["TEMPERATURE"] > threshold
        machine_df["SEGMENT_ID"] = machine_df["TEMP_BREACH"].ne(
            machine_df["TEMP_BREACH"].shift(fill_value=False)
        ).cumsum()

        breach_segments = (
            machine_df[machine_df["TEMP_BREACH"]]
            .groupby("SEGMENT_ID", as_index=False)
            .agg(
                BREACH_START=("TIMESTAMP", "min"),
                BREACH_END=("TIMESTAMP", "max"),
                BREACH_POINTS=("TIMESTAMP", "count"),
                MAX_TEMP=("TEMPERATURE", "max"),
            )
        )

        if breach_segments.empty:
            continue

        breach_segments["BREACH_DURATION_MINUTES"] = (
            breach_segments["BREACH_END"] - breach_segments["BREACH_START"]
        ).dt.total_seconds() / 60.0
        breach_segments["MACHINE_ID"] = machine_id
        breach_segments["TEMP_THRESHOLD_BASELINE"] = threshold
        breach_segments["SUSTAINED_BREACH"] = (
            breach_segments["BREACH_DURATION_MINUTES"] >= min_duration_minutes
        )
        events.append(breach_segments)

    if not events:
        return pd.DataFrame(
            columns=[
                "MACHINE_ID",
                "BREACH_START",
                "BREACH_END",
                "BREACH_POINTS",
                "MAX_TEMP",
                "BREACH_DURATION_MINUTES",
                "TEMP_THRESHOLD_BASELINE",
                "SUSTAINED_BREACH",
            ]
        )

    return pd.concat(events, ignore_index=True)[
        [
            "MACHINE_ID",
            "BREACH_START",
            "BREACH_END",
            "BREACH_POINTS",
            "MAX_TEMP",
            "BREACH_DURATION_MINUTES",
            "TEMP_THRESHOLD_BASELINE",
            "SUSTAINED_BREACH",
        ]
    ]


def build_risk_ranking(hourly: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    risk = hourly.merge(baselines, on="MACHINE_ID", how="left")
    risk["TEMP_THRESHOLD_BREACH"] = (
        risk["AVG_TEMPERATURE"] > risk["TEMP_THRESHOLD_BASELINE"]
    ).astype(int)
    risk["VIB_THRESHOLD_BREACH"] = (
        risk["AVG_VIBRATION"] > risk["VIB_THRESHOLD_BASELINE"]
    ).astype(int)

    risk["MACHINE_RISK_SCORE"] = (
        35 * risk["TEMP_THRESHOLD_BREACH"]
        + 25 * risk["VIB_THRESHOLD_BREACH"]
        + 15 * (risk["TEMP_RATE_OF_CHANGE"] >= 1.5).astype(int)
        + 10 * (risk["VIB_RATE_OF_CHANGE"] >= 0.25).astype(int)
        + 15 * (risk["ANOMALY_FLAG_RATE"] >= 0.20).astype(int)
        + 8 * (
            (risk["ANOMALY_FLAG_RATE"] >= 0.10)
            & (risk["ANOMALY_FLAG_RATE"] < 0.20)
        ).astype(int)
    ).clip(lower=0, upper=100)

    risk["MACHINE_RISK_LEVEL"] = "LOW"
    risk.loc[risk["MACHINE_RISK_SCORE"] >= 40, "MACHINE_RISK_LEVEL"] = "MEDIUM"
    risk.loc[risk["MACHINE_RISK_SCORE"] >= 70, "MACHINE_RISK_LEVEL"] = "HIGH"

    latest_risk = (
        risk.sort_values("TIMESTAMP")
        .groupby("MACHINE_ID", as_index=False)
        .tail(1)
        .sort_values(["MACHINE_RISK_SCORE", "AVG_TEMPERATURE"], ascending=False)
        .reset_index(drop=True)
    )

    return latest_risk


def save_temperature_threshold_trend(
    hourly: pd.DataFrame,
    baselines: pd.DataFrame,
    machine_id: str,
    out_dir: Path,
) -> Path:
    machine_df = hourly[hourly["MACHINE_ID"] == machine_id].copy()
    if machine_df.empty:
        raise RuntimeError(f"No hourly feature rows found for machine_id={machine_id}")

    threshold_row = baselines[baselines["MACHINE_ID"] == machine_id]
    threshold = (
        float(threshold_row["TEMP_THRESHOLD_BASELINE"].iloc[0])
        if not threshold_row.empty
        else MIN_TEMP_BASELINE
    )

    plt.figure(figsize=(12, 5))
    sns.lineplot(data=machine_df, x="TIMESTAMP", y="AVG_TEMPERATURE", linewidth=1.25)
    plt.axhline(y=threshold, color="red", linestyle="--", linewidth=1.3, label="Baseline threshold")
    plt.title(f"Hourly Temperature with Baseline - {machine_id}")
    plt.xlabel("Timestamp")
    plt.ylabel("Average Temperature")
    plt.legend()
    plt.tight_layout()

    out_path = out_dir / f"temperature_threshold_trend_{machine_id}.png"
    plt.savefig(out_path, dpi=140)
    plt.close()
    return out_path


def save_tables(
    baselines: pd.DataFrame,
    sustained_breaches: pd.DataFrame,
    risk_ranking: pd.DataFrame,
    out_dir: Path,
) -> None:
    baselines.to_csv(out_dir / "machine_baseline_summary.csv", index=False)
    sustained_breaches.to_csv(out_dir / "sustained_temp_breach_events.csv", index=False)
    risk_ranking.to_csv(out_dir / "machine_risk_ranking.csv", index=False)


def print_summary(
    sensor_df: pd.DataFrame,
    temp_vib_corr: float,
    sustained_breaches: pd.DataFrame,
    risk_ranking: pd.DataFrame,
    trend_path: Path,
) -> None:
    total_rows = len(sensor_df)
    anomaly_rows = int(sensor_df["ANOMALY_FLAG"].sum())
    anomaly_pct = (anomaly_rows / total_rows * 100.0) if total_rows else 0.0
    sustained_count = int(sustained_breaches["SUSTAINED_BREACH"].sum()) if not sustained_breaches.empty else 0

    print("=== Phase 4 Analytics Summary ===")
    print(f"Lookback days: {LOOKBACK_DAYS}")
    print(f"Total sensor rows: {total_rows}")
    print(f"Rows above baseline anomaly rule: {anomaly_rows} ({anomaly_pct:.2f}%)")
    print(f"Temperature-Vibration correlation (hourly): {temp_vib_corr:.3f}")
    print(f"Sustained temperature breaches (>= {MIN_SUSTAINED_BREACH_MINUTES} min): {sustained_count}")

    if risk_ranking.empty:
        print("Risk ranking could not be generated because no hourly data was available.")
    else:
        print("Top machine risk ranking (latest hour per machine):")
        print(risk_ranking[["MACHINE_ID", "MACHINE_RISK_SCORE", "MACHINE_RISK_LEVEL"]].to_string(index=False))

    print(f"Saved threshold trend chart: {trend_path}")
    print("Saved analytics tables: machine_baseline_summary.csv, sustained_temp_breach_events.csv, machine_risk_ranking.csv")


def main() -> None:
    sns.set_theme(style="whitegrid")
    out_dir = Path("artifacts") / "phase4"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        raw_df = load_sensor_data(conn)
    finally:
        conn.close()

    if raw_df.empty:
        raise RuntimeError("SENSOR_DATA_RAW returned no rows for the configured lookback window.")

    sensor_df = enrich_sensor_data(raw_df)
    hourly_df = build_hourly_features(sensor_df)
    baselines_df = compute_machine_baselines(hourly_df)
    sustained_breaches_df = detect_sustained_temperature_breaches(sensor_df, baselines_df)
    risk_ranking_df = build_risk_ranking(hourly_df, baselines_df)

    temp_vib_corr = correlation_analysis(hourly_df, out_dir)

    top_machine_id = (
        str(risk_ranking_df.iloc[0]["MACHINE_ID"])
        if not risk_ranking_df.empty
        else str(hourly_df.iloc[0]["MACHINE_ID"])
    )
    trend_path = save_temperature_threshold_trend(hourly_df, baselines_df, top_machine_id, out_dir)
    save_tables(baselines_df, sustained_breaches_df, risk_ranking_df, out_dir)

    print_summary(sensor_df, temp_vib_corr, sustained_breaches_df, risk_ranking_df, trend_path)


if __name__ == "__main__":
    main()
