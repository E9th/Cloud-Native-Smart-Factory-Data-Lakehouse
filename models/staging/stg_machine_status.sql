with source_data as (
    select
        nullif(trim(machine_id), '') as machine_id,
        nullif(trim(status), '') as status,
        last_updated as status_ts
    from {{ source('raw_data', 'machine_status_raw') }}
)

select
        nullif(regexp_replace(upper(machine_id), '[^A-Z0-9-]', ''), '') as machine_id,
        nullif(regexp_replace(upper(status), '[^A-Z_]', ''), '') as status,
    status_ts
from source_data
where nullif(regexp_replace(upper(machine_id), '[^A-Z0-9-]', ''), '') is not null
    and nullif(regexp_replace(upper(status), '[^A-Z_]', ''), '') is not null