select
    timestamp as event_ts,
    machine_id,
    temperature,
    vibration
from {{ source('raw_data', 'sensor_data_raw') }}
where timestamp is not null