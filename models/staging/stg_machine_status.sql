with source_data as (
    select
        nullif(trim(machine_id), '') as machine_id,
        nullif(trim(status), '') as status,
        last_updated as status_ts
    from {{ source('raw_data', 'machine_status_raw') }}
)

select
    machine_id,
    status,
    status_ts
from source_data
where machine_id is not null
  and status is not null