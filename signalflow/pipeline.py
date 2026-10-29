"""Bounded retries, immutable raw events, validation and transactional materialization."""
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy import select, update, delete
from .db import raw_events, observations, generation, runs, upsert

BASE = 'https://api.carbonintensity.org.uk'
FUELS = {'gas', 'coal', 'nuclear', 'biomass', 'hydro', 'imports', 'solar', 'wind', 'other'}
INDICES = {'very low', 'low', 'moderate', 'high', 'very high'}

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be an ISO-8601 string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp must include a timezone')
    return parsed.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def number(value, name, upper):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= upper:
        raise ValueError(f'{name} must be finite and between 0 and {upper}')
    return float(value)

def validate(kind, payload):
    if not isinstance(payload, dict):
        raise ValueError('event payload must be an object')
    start, end = timestamp(payload.get('from')), timestamp(payload.get('to'))
    if datetime.fromisoformat(end.replace('Z', '+00:00')) - datetime.fromisoformat(start.replace('Z', '+00:00')) != timedelta(minutes=30):
        raise ValueError('expected a 30-minute settlement interval')
    if kind == 'intensity':
        values = payload.get('intensity')
        if not isinstance(values, dict):
            raise ValueError('missing intensity object')
        forecast = number(values.get('forecast'), 'forecast', 2000)
        actual = None if values.get('actual') is None else number(values['actual'], 'actual', 2000)
        if values.get('index') not in INDICES:
            raise ValueError('unknown intensity index')
        return dict(start=start, end=end, forecast=forecast, actual=actual, index_label=values['index'])
    if kind != 'generation':
        raise ValueError('unknown event kind')
    mix = payload.get('generationmix')
    if not isinstance(mix, list) or not mix:
        raise ValueError('generation mix must be a nonempty list')
    seen, normalized = set(), []
    for item in mix:
        if not isinstance(item, dict) or item.get('fuel') not in FUELS or item['fuel'] in seen:
            raise ValueError('unknown or duplicate fuel')
        seen.add(item['fuel'])
        normalized.append(dict(start=start, end=end, fuel=item['fuel'], percentage=number(item.get('perc'), 'percentage', 100)))
    if abs(sum(item['percentage'] for item in normalized) - 100) > 1:
        raise ValueError('generation mix must sum to 100% (±1 rounding tolerance)')
    return normalized

def event_id(kind, payload):
    return hashlib.sha256((kind + ':' + json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=True)).encode()).hexdigest()

def process_event(engine, kind, payload):
    """At-least-once delivery, idempotent sink. Revisions get new raw hashes."""
    eid = event_id(kind, payload)
    received = now()
    try:
        normalized = validate(kind, payload)
        error = None
    except (ValueError, TypeError, KeyError) as exc:
        normalized, error = None, str(exc)
    with engine.begin() as conn:
        # Conflict-ignore claims this event inside the same transaction as its projections.
        if conn.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        claim = conn.execute(insert(raw_events).values(id=eid, kind=kind, payload=json.dumps(payload, sort_keys=True), received_at=received, status='rejected' if error else 'accepted', error=error).on_conflict_do_nothing(index_elements=['id']).returning(raw_events.c.id))
        if claim.scalar_one_or_none() is None:
            return 'duplicate'
        if error:
            return 'rejected'
        if kind == 'intensity':
            # Preserve an observed actual if a delayed forecast-only message arrives.
            existing = conn.execute(select(observations).where(observations.c.start == normalized['start'])).mappings().first()
            if existing and normalized['actual'] is None and existing['actual'] is not None:
                return 'accepted'
            upsert(conn, observations, dict(**normalized, ingested_at=received, event_id=eid), ['start'])
        else:
            conn.execute(delete(generation).where(generation.c.start == normalized[0]['start']))
            for row in normalized:
                upsert(conn, generation, dict(**row, ingested_at=received, event_id=eid), ['start', 'fuel'])
    return 'accepted'

def fetch_json(path, client=None, attempts=4, sleep=time.sleep):
    own = client is None
    client = client or httpx.Client(timeout=25, headers={'User-Agent': 'SignalFlow/1.0 (portfolio research)', 'Accept': 'application/json'})
    try:
        for attempt in range(attempts):
            try:
                response = client.get(BASE + path)
                response.raise_for_status()
                result = response.json().get('data')
                if not isinstance(result, (dict, list)):
                    raise ValueError('source response missing data')
                return result if isinstance(result, list) else [result]
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise
                if attempt == attempts - 1:
                    raise
                sleep(min(2 ** attempt, 8))
    finally:
        if own:
            client.close()

def collect(days=2, client=None):
    if not 1 <= days <= 30:
        raise ValueError('backfill days must be between 1 and 30')
    # One UTC day per request stays within source range limits.
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    for offset in reversed(range(days)):
        stop = end - timedelta(days=offset)
        start = stop - timedelta(days=1)
        window = '/' + start.strftime('%Y-%m-%dT%H:%MZ') + '/' + stop.strftime('%Y-%m-%dT%H:%MZ')
        for kind in ('intensity', 'generation'):
            for payload in fetch_json('/' + kind + window, client=client):
                yield kind, payload

def ingest(engine, days=2, events=None):
    rid = str(uuid.uuid4())
    counts = dict(fetched=0, inserted=0, rejected=0)
    with engine.begin() as conn:
        conn.execute(runs.insert().values(id=rid, started_at=now(), status='running', **counts))
    try:
        for kind, payload in (collect(days) if events is None else events):
            result = process_event(engine, kind, payload)
            counts['fetched'] += 1
            counts['inserted'] += result == 'accepted'
            counts['rejected'] += result == 'rejected'
        status, error = ('degraded' if counts['rejected'] else 'success'), None
    except Exception as exc:
        status, error = 'failed', str(exc)[:1000]
        raise
    finally:
        with engine.begin() as conn:
            conn.execute(update(runs).where(runs.c.id == rid).values(finished_at=now(), status=status, error=error, **counts))
    return dict(id=rid, status=status, **counts)
