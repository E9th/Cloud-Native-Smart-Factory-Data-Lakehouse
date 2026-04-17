with stats as (
    select
        count(*) as total_rows,
        count_if(current_status <> 'UNKNOWN') as known_rows
    from {{ ref('fct_machine_health_hourly') }}
)

select
    total_rows,
    known_rows
from stats
where total_rows > 0
  and known_rows = 0
