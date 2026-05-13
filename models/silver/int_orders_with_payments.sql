{{ config(
    materialized='table',
    database='lh_silver',
    schema='dbo'
) }}

SELECT
    o.order_id,
    o.customer_id,
    o.order_total,
    o.order_status,
    o.ordered_at,
    COALESCE(p.amount_paid, 0) AS amount_paid,
    o.order_total - COALESCE(p.amount_paid, 0) AS outstanding_balance,
    p.payment_method,
    p.payment_date
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('stg_payments') }} p
    ON o.order_id = p.order_id
