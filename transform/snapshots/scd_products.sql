{% snapshot scd_products %}
{{
    config(
      unique_key='product_id',
      strategy='timestamp',
      updated_at='updated_at',
      invalidate_hard_deletes=True,
    )
}}
select
    product_id, product_name, category, unit_price, unit_cost, unit_margin,
    created_at, updated_at
from {{ ref('stg_products') }}
{% endsnapshot %}
