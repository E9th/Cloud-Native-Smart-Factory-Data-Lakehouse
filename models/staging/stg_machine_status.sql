select
    machine_id,
    status,
    last_updated as status_ts
from {{ source('raw_data', 'MACHINE_STATUS_RAW') }}