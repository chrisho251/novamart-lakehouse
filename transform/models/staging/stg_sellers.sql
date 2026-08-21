with latest as (
    {{ latest_state('bronze', 'sellers', 'seller_id') }}
)
select
    cast(seller_id as bigint)          as seller_id,
    cast(seller_name as string)        as seller_name,
    cast(city as string)               as city,
    cast(state as string)              as state,
    cast(region as string)             as region,
    cast(fulfillment_type as string)   as fulfillment_type,
    cast(rating as double)             as rating,
    cast(created_at as timestamp)      as created_at
from latest
