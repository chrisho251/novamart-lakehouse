{{ config(materialized='table') }}

with statuses as (
    select 'placed'    as status, 1 as status_order, false as is_terminal, false as is_reversal
    union all select 'paid',      2, false, false
    union all select 'shipped',   3, false, false
    union all select 'delivered', 4, true,  false
    union all select 'canceled',  9, true,  true
    union all select 'returned',  9, true,  true
)
select
    {{ dbt_utils.generate_surrogate_key(['status']) }} as order_status_key,
    status,
    status_order,
    is_terminal,
    is_reversal
from statuses
