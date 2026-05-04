select
    o.order_id,
    o.customer_id,
    o.order_total,
    o.order_status,
    o.ordered_at,
    coalesce(p.amount_paid, 0) as amount_paid,
    o.order_total - coalesce(p.amount_paid, 0) as outstanding_balance,
    p.payment_method,
    p.payment_date
from {{ ref('stg_orders') }} o
left join {{ ref('stg_payments') }} p
    on o.order_id = p.order_id