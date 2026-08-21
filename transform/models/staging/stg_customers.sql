with latest as (
    {{ latest_state('bronze', 'customers', 'customer_id') }}
)
select
    cast(customer_id as bigint)        as customer_id,
    cast(full_name as string)          as full_name,
    lower(cast(email as string))       as email,
    cast(segment as string)            as segment,
    cast(city as string)               as city,
    cast(state as string)              as state,
    cast(region as string)             as region,
    cast(created_at as timestamp)      as created_at,
    cast(updated_at as timestamp)      as updated_at
from latest
