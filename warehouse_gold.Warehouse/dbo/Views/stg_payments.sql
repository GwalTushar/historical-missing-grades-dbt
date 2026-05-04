-- Auto Generated (Do not modify) F2A33359D7E45D383A0C246DE77B0AC58E0E8E9F284DFAAC6FB61970AA052DFD
create view "dbo"."stg_payments" as select
    id as payment_id,
    order_id,
    cast(amount as decimal(10,2)) as amount_paid,
    payment_method,
    cast(paid_at as datetime2) as payment_date
from "lakehouse_bronze"."dbo"."raw_payments";