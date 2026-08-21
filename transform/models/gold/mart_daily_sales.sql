{{ config(materialized='table') }}

-- Pre-aggregated mart powering the Streamlit homepage, so the 2X-Small
-- warehouse never scans the full fact for the dashboard.
select
    f.order_date,
    d.year,
    d.month,
    d.is_holiday_season,
    p.category,
    g.region,
    count(distinct f.order_id)          as orders,
    sum(f.quantity)                      as units,
    round(sum(f.gross_amount), 2)        as gross_revenue,
    round(sum(f.discount_amount), 2)     as discounts,
    round(sum(f.net_amount), 2)          as net_revenue,
    round(sum(f.margin_amount), 2)       as margin,
    round(sum(f.net_amount) / nullif(count(distinct f.order_id), 0), 2) as avg_order_value
from {{ ref('fct_order_items') }} f
left join {{ ref('dim_date') }} d on f.date_key = d.date_key
left join {{ ref('dim_product') }} p on f.product_key = p.product_key
left join {{ ref('dim_geography') }} g on f.geography_key = g.geography_key
group by 1, 2, 3, 4, 5, 6
