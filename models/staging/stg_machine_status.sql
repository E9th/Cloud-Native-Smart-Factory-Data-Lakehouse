select
    machine_id,
    status,
    last_updated as status_ts
from {{ source('raw_data', 'machine_status_raw') }}