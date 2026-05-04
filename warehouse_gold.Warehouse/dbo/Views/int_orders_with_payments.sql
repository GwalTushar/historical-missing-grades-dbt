-- Auto Generated (Do not modify) C36A94199894FA4461261002FB8D35E9EBD18312E0EEC1AED96CDD1854B8486F
create view "dbo"."int_orders_with_payments" as select
    o.order_id,
    o.customer_id,
    o.order_total,
    o.order_status,
    o.ordered_at,
    coalesce(p.amount_paid, 0) as amount_paid,
    o.order_total - coalesce(p.amount_paid, 0) as outstanding_balance,
    p.payment_method,
    p.payment_date
from "warehouse_gold"."dbo"."stg_orders" o
left join "warehouse_gold"."dbo"."stg_payments" p
    on o.order_id = p.order_id;