-- Auto Generated (Do not modify) C06FB4476B3416B2F76C6371E74CE8DA554D751D851801786BFD3B05A0438646
create view "dbo"."stg_orders" as select
    id as order_id,
    customer_id,
    cast(total as decimal(10,2)) as order_total,
    status as order_status,
    cast(created_at as datetime2) as ordered_at
from "lakehouse_bronze"."dbo"."raw_orders";