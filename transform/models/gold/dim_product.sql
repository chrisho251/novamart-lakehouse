{{ config(materialized='table') }}

select
    {{ dbt_utils.generate_surrogate_key(['product_id', 'dbt_valid_from']) }} as product_key,
    product_id,
    product_name,
    category,
    unit_price,
    unit_cost,
    unit_margin,
    case
        when unit_price < 25 then 'budget'
        when unit_price < 150 then 'mid'
        when unit_price < 600 then 'premium'
        else 'luxury'
    end                                     as price_band,
    dbt_valid_from                          as valid_from,
    coalesce(dbt_valid_to, timestamp('9999-12-31')) as valid_to,
    dbt_valid_to is null                    as is_current
from {{ ref('scd_products') }}
