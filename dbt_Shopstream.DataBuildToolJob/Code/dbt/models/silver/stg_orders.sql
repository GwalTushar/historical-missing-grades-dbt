select
    id as order_id,
    customer_id,
    cast(total as decimal(10,2)) as order_total,
    status as order_status,
    cast(created_at as datetime2) as ordered_at
from {{ source('bronze', 'raw_orders') }}