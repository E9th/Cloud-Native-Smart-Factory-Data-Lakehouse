select
    order_id,
    machine_id,
    product_name,
    target_quantity,
    order_status,
    created_at
from {{ source('raw_data', 'WORK_ORDERS_RAW') }}