{% snapshot scd_customers %}
{{
    config(
      unique_key='customer_id',
      strategy='timestamp',
      updated_at='updated_at',
      invalidate_hard_deletes=True,
    )
}}
select
    customer_id, full_name, email, segment, city, state, region,
    created_at, updated_at
from {{ ref('stg_customers') }}
{% endsnapshot %}
