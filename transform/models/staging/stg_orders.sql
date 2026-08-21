with latest as (
    {{ latest_state('bronze', 'orders', 'order_id') }}
)
select
    cast(order_id as bigint)           as order_id,
    cast(customer_id as bigint)        as customer_id,
    cast(seller_id as bigint)          as seller_id,
    cast(status as string)             as status,
    cast(order_ts as timestamp)        as order_ts,
    cast(updated_at as timestamp)      as updated_at,
    to_date(order_ts)                  as order_date,
    status in ('delivered')            as is_completed,
    status in ('canceled', 'returned') as is_reversed
from latest
