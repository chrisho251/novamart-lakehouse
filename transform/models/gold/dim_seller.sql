{{ config(materialized='table') }}

select
    {{ dbt_utils.generate_surrogate_key(['seller_id']) }} as seller_key,
    seller_id,
    seller_name,
    city,
    state,
    region,
    fulfillment_type,
    rating,
    case
        when rating >= 4.5 then 'top'
        when rating >= 4.0 then 'good'
        else 'standard'
    end as rating_tier
from {{ ref('stg_sellers') }}
