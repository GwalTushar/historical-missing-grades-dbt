{{ config(
    materialized='table',
    database='lh_silver',
    schema='dbo'
) }}

SELECT
    id AS customer_id,
    first_name,
    last_name,
    email,
    CAST(created_at AS TIMESTAMP) AS customer_created_at
FROM {{ source('bronze', 'raw_customers') }}
