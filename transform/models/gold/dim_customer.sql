{{ config(materialized='table') }}

-- SCD-2 customer dimension sourced from the snapshot: one row per historical
-- version, so a fact can be attributed to attributes true at order time.
select
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'dbt_valid_from']) }} as customer_key,
    customer_id,
    full_name,
    email,
    segment,
    city,
    state,
    region,
    created_at,
    dbt_valid_from                          as valid_from,
    coalesce(dbt_valid_to, timestamp('9999-12-31')) as valid_to,
    dbt_valid_to is null                    as is_current
from {{ ref('scd_customers') }}
