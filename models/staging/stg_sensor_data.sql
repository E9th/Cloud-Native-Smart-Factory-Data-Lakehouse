with source_data as (
    select
        timestamp as event_ts,
        nullif(trim(machine_id), '') as machine_id,
        temperature,
        vibration
    from {{ source('raw_data', 'sensor_data_raw') }}
)

select
    event_ts,
    upper(machine_id) as machine_id,
    temperature,
    vibration
from source_data
where event_ts is not null
  and machine_id is not null