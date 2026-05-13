{{ config(
    materialized='table',
    database='lh_silver',
    schema='dbo'
) }}

SELECT
    id AS order_id,
    customer_id,
    CAST(total AS DECIMAL(10,2)) AS order_total,
    status AS order_status,
    CAST(created_at AS TIMESTAMP) AS ordered_at
FROM {{ source('bronze', 'raw_orders') }}
