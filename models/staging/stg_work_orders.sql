with source_data as (
    select
        nullif(trim(order_id), '') as order_id,
        nullif(trim(machine_id), '') as machine_id,
        product_name,
        target_quantity,
        order_status,
        created_at
    from {{ source('raw_data', 'work_orders_raw') }}
),

filtered as (
    select
        order_id,
        machine_id,
        product_name,
        target_quantity,
        order_status,
        created_at
    from source_data
    where order_id is not null
      and machine_id is not null
)

select
    order_id,
    machine_id,
    product_name,
    target_quantity,
    order_status,
    created_at
from filtered
qualify row_number() over (
    partition by order_id
    order by created_at desc nulls last
) = 1