with latest as (
    {{ latest_state('bronze', 'products', 'product_id') }}
)
select
    cast(product_id as bigint)         as product_id,
    cast(product_name as string)       as product_name,
    cast(category as string)           as category,
    cast(unit_price as double)         as unit_price,
    cast(unit_cost as double)          as unit_cost,
    cast(unit_price - unit_cost as double) as unit_margin,
    cast(created_at as timestamp)      as created_at,
    cast(updated_at as timestamp)      as updated_at
from latest
