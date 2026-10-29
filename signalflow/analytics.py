"""Deterministic metrics; missing actuals never become observed zeroes."""
from datetime import datetime, timezone
from statistics import mean, pstdev
from sqlalchemy import select, func
from .db import observations, generation, raw_events, runs
from .pipeline import now

RENEWABLE = {'wind', 'solar', 'hydro'}

def snapshot(engine, hours=48):
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(select(observations).order_by(observations.c.start.desc()).limit(min(hours * 2, 1440))).mappings()][::-1]
        # Time window is relative to the newest available interval, with actual gaps retained.
        if rows:
            latest_ts = datetime.fromisoformat(rows[-1]['end'].replace('Z', '+00:00')).timestamp()
            rows = [r for r in rows if datetime.fromisoformat(r['end'].replace('Z', '+00:00')).timestamp() > latest_ts - hours * 3600]
        mix_start = conn.execute(select(func.max(generation.c.start))).scalar()
        mix = [dict(r) for r in conn.execute(select(generation).where(generation.c.start == mix_start).order_by(generation.c.percentage.desc())).mappings()] if mix_start else []
        recent_runs = [dict(r) for r in conn.execute(select(runs).order_by(runs.c.started_at.desc()).limit(12)).mappings()]
        quality = dict(conn.execute(select(raw_events.c.status, func.count()).group_by(raw_events.c.status)).all())
        total = conn.execute(select(func.count()).select_from(observations)).scalar()
        quarantined = [dict(r) for r in conn.execute(select(raw_events.c.id, raw_events.c.kind, raw_events.c.error, raw_events.c.received_at).where(raw_events.c.status == 'rejected').order_by(raw_events.c.received_at.desc()).limit(10)).mappings()]
    anomalies = []
    for i, row in enumerate(rows):
        previous = [r['actual'] for r in rows[max(0, i - 48):i] if r['actual'] is not None]
        row['anomaly'] = False
        if row['actual'] is not None and len(previous) >= 12:
            average, spread = mean(previous), max(pstdev(previous), 10)
            z = (row['actual'] - average) / spread
            if abs(z) >= 3:
                row['anomaly'] = True
                anomalies.append(dict(start=row['start'], actual=row['actual'], baseline=round(average, 1), z_score=round(z, 2), severity='high' if abs(z) >= 4 else 'warning'))
    actual_rows = [r for r in rows if r['actual'] is not None]
    latest = rows[-1] if rows else None
    age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(latest['end'].replace('Z', '+00:00'))).total_seconds()) if latest else None
    mix_age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(mix[0]['end'].replace('Z', '+00:00'))).total_seconds()) if mix else None
    status = 'empty' if latest is None else 'stale' if age > 5400 or mix_age is None or mix_age > 5400 else 'healthy'
    if recent_runs and recent_runs[0]['status'] in ('failed', 'degraded'):
        status = 'degraded'
    best = min(rows, key=lambda r: r['forecast']) if rows else None
    return dict(generated_at=now(), status=status, source='NESO Carbon Intensity API · Great Britain',
        source_url='https://api.carbonintensity.org.uk/', interval_minutes=30, scope='National grid signals; not data-center telemetry or electricity prices',
        metrics=dict(latest=latest, average_actual=round(mean([r['actual'] for r in actual_rows]), 1) if actual_rows else None,
            forecast_mae=round(mean([abs(r['actual'] - r['forecast']) for r in actual_rows]), 1) if actual_rows else None,
            actual_coverage=round(len(actual_rows) / len(rows) * 100, 1) if rows else None,
            renewable_percentage=round(sum(r['percentage'] for r in mix if r['fuel'] in RENEWABLE), 1) if mix else None,
            freshness_seconds=age, generation_freshness_seconds=mix_age, total_intervals=total, window_intervals=len(rows),
            accepted_events=quality.get('accepted', 0), rejected_events=quality.get('rejected', 0),
            best_interval=best), series=rows, generation=mix, anomalies=anomalies, runs=recent_runs, quarantine=quarantined)

def scenario(data, power_kw, duration_hours, pue):
    rows = data['series']
    # This is a historical comparison, not a forecast or scheduler.
    candidates = []
    needed = int(duration_hours * 2)
    for i in range(len(rows) - needed + 1):
        window = rows[i:i + needed]
        if any(r['actual'] is None for r in window):
            continue
        timestamps = [datetime.fromisoformat(r['start'].replace('Z', '+00:00')).timestamp() for r in window]
        if any(b - a != 1800 for a, b in zip(timestamps, timestamps[1:])):
            continue
        candidates.append(dict(start=window[0]['start'], end=window[-1]['end'], intensity=mean([r['actual'] for r in window])))
    if not candidates:
        return dict(available=False, reason='Not enough contiguous observed intervals for this duration.')
    best, worst = min(candidates, key=lambda c: c['intensity']), max(candidates, key=lambda c: c['intensity'])
    energy = power_kw * duration_hours * pue
    return dict(available=True, energy_kwh=round(energy, 2), best=best, worst=worst,
        best_kg=round(energy * best['intensity'] / 1000, 3), worst_kg=round(energy * worst['intensity'] / 1000, 3),
        avoided_kg=round(energy * (worst['intensity'] - best['intensity']) / 1000, 3),
        method='Historical location-based estimate: IT kW × hours × PUE × grid gCO₂/kWh ÷ 1000. Excludes embodied emissions; no claim of future savings.')
