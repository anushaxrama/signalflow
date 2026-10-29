select
    cast(start as timestamptz) as interval_start,
    cast("end" as timestamptz) as interval_end,
    forecast as forecast_gco2_kwh,
    actual as actual_gco2_kwh,
    actual - forecast as forecast_error_gco2_kwh,
    index_label,
    cast(ingested_at as timestamptz) as ingested_at,
    event_id
from {{ source('grid', 'observations') }}
