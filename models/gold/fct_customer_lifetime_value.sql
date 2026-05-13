{{ config(materialized='table') }}

SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    COUNT(o.order_id) AS total_orders,
    COALESCE(SUM(o.order_total), 0) AS lifetime_spend,
    COALESCE(SUM(o.outstanding_balance), 0) AS total_outstanding,
    MIN(o.ordered_at) AS first_order_date,
    MAX(o.ordered_at) AS last_order_date
FROM {{ source('silver', 'stg_customers') }} c
LEFT JOIN {{ source('silver', 'int_orders_with_payments') }} o
    ON c.customer_id = o.customer_id
GROUP BY
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email
