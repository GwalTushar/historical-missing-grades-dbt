select
    id as customer_id,
    first_name,
    last_name,
    email,
    cast(created_at as datetime2) as customer_created_at
from {{ source('bronze', 'raw_customers') }}