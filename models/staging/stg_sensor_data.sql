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
    nullif(regexp_replace(upper(machine_id), '[^A-Z0-9-]', ''), '') as machine_id,
    temperature,
    vibration
from source_data
where event_ts is not null
  and nullif(regexp_replace(upper(machine_id), '[^A-Z0-9-]', ''), '') is not null