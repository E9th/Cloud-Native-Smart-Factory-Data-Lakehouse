with sensor as (
    select
        date_trunc('hour', event_ts) as hour_ts,
        machine_id,
        regexp_replace(upper(machine_id), '[^A-Z0-9]', '') as machine_key,
        avg(temperature) as avg_temperature,
        avg(vibration) as avg_vibration,
        sum(case when temperature > 90 or vibration > 2.0 then 1 else 0 end) as anomaly_events,
        count(*) as total_events
    from {{ ref('stg_sensor_data') }}
    group by 1, 2, 3
),

latest_status as (
    select machine_key, status
    from (
        select
            regexp_replace(upper(machine_id), '[^A-Z0-9]', '') as machine_key,
            status,
            status_ts,
            row_number() over (
                partition by regexp_replace(upper(machine_id), '[^A-Z0-9]', '')
                order by status_ts desc
            ) as rn
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
left join latest_status ls
    on s.machine_key = ls.machine_key