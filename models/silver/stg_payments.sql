{{ config(
    materialized='table',
    database='lh_silver',
    schema='dbo'
) }}

SELECT
    id AS payment_id,
    order_id,
    CAST(amount AS DECIMAL(10,2)) AS amount_paid,
    payment_method,
    CAST(paid_at AS TIMESTAMP) AS payment_date
FROM {{ source('bronze', 'raw_payments') }}
