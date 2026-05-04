select
    id as payment_id,
    order_id,
    cast(amount as decimal(10,2)) as amount_paid,
    payment_method,
    cast(paid_at as datetime2) as payment_date
from {{ source('bronze', 'raw_payments') }}