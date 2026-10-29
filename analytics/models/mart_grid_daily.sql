select
    cast(interval_start at time zone 'UTC' as date) as day_utc,
    count(*) as interval_count,
    count(actual_gco2_kwh) as observed_count,
    round(100.0 * count(actual_gco2_kwh) / nullif(count(*), 0), 2) as actual_coverage_pct,
    avg(actual_gco2_kwh) as avg_actual_gco2_kwh,
    min(actual_gco2_kwh) as min_actual_gco2_kwh,
    max(actual_gco2_kwh) as max_actual_gco2_kwh,
    avg(abs(forecast_error_gco2_kwh)) as forecast_mae_gco2_kwh
from {{ ref('stg_grid_intervals') }}
group by 1
