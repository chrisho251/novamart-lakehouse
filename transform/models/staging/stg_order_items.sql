with latest as (
    {{ latest_state('bronze', 'order_items', 'order_item_id') }}
)
select
    cast(order_item_id as bigint)      as order_item_id,
    cast(order_id as bigint)           as order_id,
    cast(product_id as bigint)         as product_id,
    cast(quantity as int)              as quantity,
    cast(unit_price as double)         as unit_price,
    cast(discount_pct as double)       as discount_pct,
    cast(net_amount as double)         as net_amount,
    cast(quantity * unit_price as double) as gross_amount,
    cast(quantity * unit_price * discount_pct as double) as discount_amount
from latest
