with hourly as (
    select
        hour_ts,
        machine_id,
        avg_temperature,
        avg_vibration,
        anomaly_events,
        total_events,
        current_status
    from {{ ref('fct_machine_health_hourly') }}
),

baseline as (
    select
        machine_id,
        percentile_cont(0.95) within group (order by avg_temperature) as machine_temp_p95,
        percentile_cont(0.95) within group (order by avg_vibration) as machine_vibration_p95
    from hourly
    group by 1
),

features as (
    select
        h.hour_ts,
        h.machine_id,
        h.avg_temperature,
        h.avg_vibration,
        h.anomaly_events,
        h.total_events,
        h.current_status,
        avg(h.avg_temperature) over (
            partition by h.machine_id
            order by h.hour_ts
            rows between 2 preceding and current row
        ) as rolling_mean_temp_3h,
        stddev_pop(h.avg_temperature) over (
            partition by h.machine_id
            order by h.hour_ts
            rows between 2 preceding and current row
        ) as rolling_std_temp_3h,
        avg(h.avg_vibration) over (
            partition by h.machine_id
            order by h.hour_ts
            rows between 2 preceding and current row
        ) as rolling_mean_vibration_3h,
        stddev_pop(h.avg_vibration) over (
            partition by h.machine_id
            order by h.hour_ts
            rows between 2 preceding and current row
        ) as rolling_std_vibration_3h,
        h.avg_temperature
        - lag(h.avg_temperature) over (
            partition by h.machine_id
            order by h.hour_ts
        ) as temp_rate_of_change,
        h.avg_vibration
        - lag(h.avg_vibration) over (
            partition by h.machine_id
            order by h.hour_ts
        ) as vibration_rate_of_change,
        sum(h.anomaly_events) over (
            partition by h.machine_id
            order by h.hour_ts
            rows between 2 preceding and current row
        )
        / nullif(
            sum(h.total_events) over (
                partition by h.machine_id
                order by h.hour_ts
                rows between 2 preceding and current row
            ),
            0
        ) as anomaly_rate_3h
    from hourly h
),

scored as (
    select
        f.hour_ts,
        f.machine_id,
        f.avg_temperature,
        f.avg_vibration,
        f.anomaly_events,
        f.total_events,
        f.current_status,
        f.rolling_mean_temp_3h,
        coalesce(f.rolling_std_temp_3h, 0) as rolling_std_temp_3h,
        f.rolling_mean_vibration_3h,
        coalesce(f.rolling_std_vibration_3h, 0) as rolling_std_vibration_3h,
        coalesce(f.temp_rate_of_change, 0) as temp_rate_of_change,
        coalesce(f.vibration_rate_of_change, 0) as vibration_rate_of_change,
        coalesce(f.anomaly_rate_3h, 0) as anomaly_rate_3h,
        b.machine_temp_p95,
        b.machine_vibration_p95,
        greatest(85.0, b.machine_temp_p95) as temp_threshold_baseline,
        greatest(2.0, b.machine_vibration_p95) as vibration_threshold_baseline,
        case
            when f.avg_temperature > greatest(85.0, b.machine_temp_p95) then 1
            else 0
        end as temp_threshold_breach,
        case
            when f.avg_vibration > greatest(2.0, b.machine_vibration_p95) then 1
            else 0
        end as vibration_threshold_breach
    from features f
    inner join baseline b
        on f.machine_id = b.machine_id
),

risk as (
    select
        *,
        least(
            100,
            greatest(
                0,
                (
                    case when temp_threshold_breach = 1 then 35 else 0 end
                    + case when vibration_threshold_breach = 1 then 25 else 0 end
                    + case when temp_rate_of_change >= 1.5 then 15 else 0 end
                    + case when vibration_rate_of_change >= 0.25 then 10 else 0 end
                    + case
                        when anomaly_rate_3h >= 0.20 then 15
                        when anomaly_rate_3h >= 0.10 then 8
                        else 0
                    end
                )
            )
        ) as machine_risk_score
    from scored
)

select
    hour_ts,
    machine_id,
    avg_temperature,
    avg_vibration,
    anomaly_events,
    total_events,
    current_status,
    rolling_mean_temp_3h,
    rolling_std_temp_3h,
    rolling_mean_vibration_3h,
    rolling_std_vibration_3h,
    temp_rate_of_change,
    vibration_rate_of_change,
    anomaly_rate_3h,
    machine_temp_p95,
    machine_vibration_p95,
    temp_threshold_baseline,
    vibration_threshold_baseline,
    temp_threshold_breach,
    vibration_threshold_breach,
    machine_risk_score,
    case
        when machine_risk_score >= 70 then 'HIGH'
        when machine_risk_score >= 40 then 'MEDIUM'
        else 'LOW'
    end as machine_risk_level
from risk
