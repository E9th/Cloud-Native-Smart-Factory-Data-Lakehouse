with base as (
    select
        coalesce(created_at, to_timestamp_ntz('1970-01-01 00:00:00')) as created_at_filled,
        machine_id,
        coalesce(order_status, 'UNKNOWN') as order_status,
        coalesce(target_quantity, 0) as target_quantity
    from {{ ref('stg_work_orders') }}
    where machine_id is not null
)

select
    date_trunc('day', created_at_filled) as order_day,
    machine_id,
    order_status,
    count(*) as order_count,
    sum(target_quantity) as target_quantity_sum
from base
group by 1, 2, 3