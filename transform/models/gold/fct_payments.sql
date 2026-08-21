{{ config(materialized='table') }}

-- Grain: one row per payment. Shares dim_date, dim_customer and
-- dim_payment_method with fct_order_items (conformed dimensions).
with pay as (
    select * from {{ ref('stg_payments') }}
),
orders as (
    select * from {{ ref('stg_orders') }}
)
select
    pay.payment_id,
    pay.order_id,

    cast(date_format(coalesce(pay.paid_ts, o.order_ts), 'yyyyMMdd') as int) as date_key,
    c.customer_key,
    pm.payment_method_key,

    pay.payment_status,
    pay.installments,
    o.status                       as order_status,
    coalesce(pay.paid_ts, o.order_ts) as event_ts,

    -- measures
    pay.amount                     as payment_amount,
    case when pay.payment_status = 'captured' then pay.amount else 0 end as captured_amount,
    cast(pay.amount / nullif(pay.installments, 0) as double) as installment_amount
from pay
join orders o
    on pay.order_id = o.order_id
left join {{ ref('dim_customer') }} c
    on o.customer_id = c.customer_id
   and o.order_ts >= c.valid_from and o.order_ts < c.valid_to
left join {{ ref('dim_payment_method') }} pm
    on pay.payment_method = pm.payment_method
