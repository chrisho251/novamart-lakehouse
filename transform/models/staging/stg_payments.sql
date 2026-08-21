with latest as (
    {{ latest_state('bronze', 'payments', 'payment_id') }}
)
select
    cast(payment_id as bigint)         as payment_id,
    cast(order_id as bigint)           as order_id,
    cast(payment_method as string)     as payment_method,
    cast(installments as int)          as installments,
    cast(amount as double)             as amount,
    cast(status as string)             as payment_status,
    cast(paid_ts as timestamp)         as paid_ts,
    to_date(paid_ts)                   as paid_date
from latest
