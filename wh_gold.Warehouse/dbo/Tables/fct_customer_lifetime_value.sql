CREATE TABLE [dbo].[fct_customer_lifetime_value] (

	[customer_id] int NULL, 
	[first_name] varchar(8000) NULL, 
	[last_name] varchar(8000) NULL, 
	[email] varchar(8000) NULL, 
	[total_orders] int NULL, 
	[lifetime_spend] decimal(38,2) NULL, 
	[total_outstanding] decimal(38,2) NULL, 
	[first_order_date] datetime2(6) NULL, 
	[last_order_date] datetime2(6) NULL
);