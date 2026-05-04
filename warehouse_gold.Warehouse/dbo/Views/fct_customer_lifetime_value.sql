-- Auto Generated (Do not modify) 7F8DA637E60C6CCB40056F671EE8E5766341CAD044A1626775465BE50D70498E
create view "dbo"."fct_customer_lifetime_value" as select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    count(o.order_id) as total_orders,
    coalesce(sum(o.order_total), 0) as lifetime_spend,
    coalesce(sum(o.outstanding_balance), 0) as total_outstanding,
    min(o.ordered_at) as first_order_date,
    max(o.ordered_at) as last_order_date
from "warehouse_gold"."dbo"."stg_customers" c
left join "warehouse_gold"."dbo"."int_orders_with_payments" o
    on c.customer_id = o.customer_id
group by
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email;