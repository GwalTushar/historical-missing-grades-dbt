-- Auto Generated (Do not modify) 6B3C0B39D6F8586E064C4D5F28BF55148AB5B08540D0C6EB0EF800F3198A4542
create view "dbo"."stg_customers" as select
    id as customer_id,
    first_name,
    last_name,
    email,
    cast(created_at as datetime2) as customer_created_at
from "lakehouse_bronze"."dbo"."raw_customers";