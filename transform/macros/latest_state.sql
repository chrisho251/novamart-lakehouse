{#
  Collapse a bronze CDC table to the latest, non-deleted state per primary key.
  Works for both batch loads (_op='r') and CDC (_op in c/u/d), because both
  populate _event_ts_ms and _deleted.
#}
{% macro latest_state(source_name, table_name, primary_key) %}
    select * except(_rn)
    from (
        select
            *,
            row_number() over (
                partition by {{ primary_key }}
                order by _event_ts_ms desc, _ingested_at desc
            ) as _rn
        from {{ source(source_name, table_name) }}
    )
    where _rn = 1
      and not coalesce(_deleted, false)
{% endmacro %}
