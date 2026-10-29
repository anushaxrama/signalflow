select * from {{ ref('stg_grid_intervals') }}
where interval_end - interval_start != interval '30 minutes'
   or forecast_gco2_kwh < 0 or actual_gco2_kwh < 0
   or forecast_gco2_kwh > 2000 or actual_gco2_kwh > 2000
