select
    date_trunc('day', created_at) as order_day,
    machine_id,
    order_status,
    count(*) as order_count,
    sum(target_quantity) as target_quantity_sum
from {{ ref('stg_work_orders') }}
where created_at is not null
group by 1, 2, 3