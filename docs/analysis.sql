-- PostgreSQL analysis examples. Execute after ingestion. All day groupings are UTC.

-- 1. Observed daily intensity, volatility and forecast error.
select
    cast(cast(start as timestamptz) at time zone 'UTC' as date) as day_utc,
    count(*) as stored_intervals,
    count(actual) as observed_intervals,
    avg(actual) as mean_gco2_kwh,
    stddev_pop(actual) as volatility_gco2_kwh,
    avg(abs(actual - forecast)) as forecast_mae_gco2_kwh
from observations
group by 1 order by 1;

-- 2. Mean renewable share, using an explicit product definition.
with renewable as (
    select start, sum(case when fuel in ('wind', 'solar', 'hydro') then percentage else 0 end) as share
    from generation group by start
)
select cast(cast(start as timestamptz) at time zone 'UTC' as date) as day_utc,
       avg(share) as mean_renewable_pct
from renewable group by 1 order by 1;

-- 3. Missing expected intervals (different from null-actual coverage).
with bounds as (
    select min(cast(start as timestamptz)) as lo, max(cast(start as timestamptz)) as hi from observations
), expected as (
    select generate_series(lo, hi, interval '30 minutes') as expected_start from bounds
)
select e.expected_start
from expected e
left join observations o on cast(o.start as timestamptz) = e.expected_start
where o.start is null order by 1;

-- 4. Lowest observed two-hour contiguous window, no forecast substitution.
with windows as (
    select cast(start as timestamptz) as window_start,
           lead(cast(start as timestamptz), 3) over w as last_start,
           count(actual) over (order by start rows between current row and 3 following) as actual_count,
           avg(actual) over (order by start rows between current row and 3 following) as avg_intensity
    from observations
    window w as (order by start)
)
select window_start, window_start + interval '2 hours' as window_end,
       avg_intensity,
       100 * 2 * 1.2 * avg_intensity / 1000 as example_kgco2
from windows
where actual_count = 4 and last_start - window_start = interval '90 minutes'
order by avg_intensity limit 1;

-- 5. Quarantine audit and source revisions.
select kind, status, count(*) as events from raw_events group by kind, status;
select started_at, status, fetched, inserted, rejected, error
from pipeline_runs order by started_at desc limit 20;
