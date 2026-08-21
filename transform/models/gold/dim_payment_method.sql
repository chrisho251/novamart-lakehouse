{{ config(materialized='table') }}

with methods as (
    select 'credit_card' as payment_method, true  as supports_installments, 'card'    as method_group
    union all select 'debit_card',  false, 'card'
    union all select 'pix',         false, 'instant_transfer'
    union all select 'boleto',      false, 'voucher'
    union all select 'wallet',      false, 'digital_wallet'
)
select
    {{ dbt_utils.generate_surrogate_key(['payment_method']) }} as payment_method_key,
    payment_method,
    method_group,
    supports_installments
from methods
