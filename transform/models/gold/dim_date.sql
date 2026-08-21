{{ config(materialized='table') }}

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('date_start') ~ "' as date)",
        end_date="cast('" ~ var('date_end') ~ "' as date)"
    ) }}
),
final as (
    select
        cast(date_format(date_day, 'yyyyMMdd') as int) as date_key,
        date_day                                       as date,
        year(date_day)                                 as year,
        quarter(date_day)                              as quarter,
        month(date_day)                                as month,
        date_format(date_day, 'MMMM')                  as month_name,
        weekofyear(date_day)                           as week_of_year,
        dayofweek(date_day)                            as day_of_week,
        date_format(date_day, 'EEEE')                  as day_name,
        case when dayofweek(date_day) in (1, 7) then true else false end as is_weekend,
        case when month(date_day) in (11, 12) then true else false end   as is_holiday_season
    from spine
)
select * from final
