{{ config(materialized='table') }}

-- Conformed location dimension built from every place a customer or seller sits.
with places as (
    select city, state, region from {{ ref('stg_customers') }}
    union
    select city, state, region from {{ ref('stg_sellers') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['city', 'state', 'region']) }} as geography_key,
    city,
    state,
    region
from places
where city is not null
group by city, state, region
