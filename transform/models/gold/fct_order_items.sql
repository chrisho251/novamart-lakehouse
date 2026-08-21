{{ config(
    materialized='table',
    partition_by=['order_date'],
) }}

-- Grain: one row per order line item.
-- SCD-2 dimensions (customer, product) are joined *as of order time* so revenue
-- is attributed to the attributes that were true when the order was placed.
with items as (
    select * from {{ ref('stg_order_items') }}
),
orders as (
    select * from {{ ref('stg_orders') }}
),
payments as (
    select order_id, payment_method
    from {{ ref('stg_payments') }}
)
select
    i.order_item_id,
    i.order_id,

    -- foreign keys
    cast(date_format(o.order_ts, 'yyyyMMdd') as int) as date_key,
    c.customer_key,
    p.product_key,
    s.seller_key,
    st.order_status_key,
    g.geography_key,
    pm.payment_method_key,

    -- degenerate / descriptive
    o.status                                     as order_status,
    o.order_ts,
    o.order_date,

    -- additive measures
    i.quantity,
    i.gross_amount,
    i.discount_amount,
    i.net_amount,
    cast(i.quantity * p.unit_cost as double)     as cost_amount,
    cast(i.net_amount - (i.quantity * p.unit_cost) as double) as margin_amount
from items i
join orders o
    on i.order_id = o.order_id
left join {{ ref('dim_customer') }} c
    on o.customer_id = c.customer_id
   and o.order_ts >= c.valid_from and o.order_ts < c.valid_to
left join {{ ref('dim_product') }} p
    on i.product_id = p.product_id
   and o.order_ts >= p.valid_from and o.order_ts < p.valid_to
left join {{ ref('dim_seller') }} s
    on o.seller_id = s.seller_id
left join {{ ref('dim_order_status') }} st
    on o.status = st.status
left join {{ ref('dim_geography') }} g
    on c.city = g.city and c.state = g.state and c.region = g.region
left join payments pay
    on o.order_id = pay.order_id
left join {{ ref('dim_payment_method') }} pm
    on pay.payment_method = pm.payment_method
