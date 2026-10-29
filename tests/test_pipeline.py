import copy
import httpx
import pytest
from sqlalchemy import select, func
from signalflow.db import raw_events, observations, generation, runs
from signalflow.pipeline import process_event, validate, fetch_json, ingest, collect

def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar()

def test_replay_is_idempotent(engine, intensity):
    assert process_event(engine, 'intensity', intensity) == 'accepted'
    assert process_event(engine, 'intensity', intensity) == 'duplicate'
    assert count(engine, observations) == count(engine, raw_events) == 1

def test_actual_revisions_and_delayed_forecasts(engine, intensity):
    forecast = copy.deepcopy(intensity)
    forecast['intensity']['actual'] = None
    process_event(engine, 'intensity', forecast)
    process_event(engine, 'intensity', intensity)
    forecast['intensity']['forecast'] = 105
    process_event(engine, 'intensity', forecast)
    with engine.connect() as conn:
        row = conn.execute(select(observations)).mappings().one()
    assert row['actual'] == 110
    assert row['forecast'] == 100
    assert count(engine, raw_events) == 3

@pytest.mark.parametrize('bad', [-1, 2001, True, '20', float('inf')])
def test_invalid_numbers_quarantined(engine, intensity, bad):
    intensity['intensity']['actual'] = bad
    assert process_event(engine, 'intensity', intensity) == 'rejected'
    assert count(engine, observations) == 0
    with engine.connect() as conn:
        assert conn.execute(select(raw_events.c.error)).scalar()

def test_naive_timestamp_rejected(intensity):
    intensity['from'] = '2026-10-01T00:00'
    with pytest.raises(ValueError, match='timezone'):
        validate('intensity', intensity)

def test_bad_interval_rejected(intensity):
    intensity['to'] = '2026-10-01T01:00Z'
    with pytest.raises(ValueError, match='30-minute'):
        validate('intensity', intensity)

def test_null_actual_allowed(intensity):
    intensity['intensity']['actual'] = None
    assert validate('intensity', intensity)['actual'] is None

def test_generation_totals_and_duplicates(engine, mix):
    assert process_event(engine, 'generation', mix) == 'accepted'
    assert count(engine, generation) == 2
    mix['generationmix'][0]['perc'] = 20
    assert process_event(engine, 'generation', mix) == 'rejected'
    mix['generationmix'] = [{'fuel':'gas','perc':50},{'fuel':'gas','perc':50}]
    assert process_event(engine, 'generation', mix) == 'rejected'

def test_source_retry_then_success():
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(503) if len(calls)<3 else httpx.Response(200,json={'data':[{'ok':True}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert fetch_json('/intensity',client=client,sleep=lambda _:None) == [{'ok':True}]
    assert len(calls)==3

def test_retry_exhaustion():
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(429))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_json('/intensity',client=client,attempts=2,sleep=lambda _:None)

def test_run_failure_is_durable(engine, intensity):
    def fail():
        yield 'intensity', intensity
        raise RuntimeError('source unavailable')
    with pytest.raises(RuntimeError):
        ingest(engine,events=fail())
    assert count(engine, observations)==1
    with engine.connect() as conn:
        row=conn.execute(select(runs)).mappings().one()
    assert row['status']=='failed' and row['fetched']==1 and row['finished_at']

def test_degraded_run(engine, intensity):
    intensity['intensity']['forecast']=-5
    assert ingest(engine,events=[('intensity',intensity)])['status']=='degraded'

@pytest.mark.parametrize('days',[0,31])
def test_backfill_boundaries(days):
    with pytest.raises(ValueError):
        list(collect(days))


def test_revised_mix_replaces_all_fuels(engine, mix):
    process_event(engine, 'generation', mix)
    mix['generationmix']=[{'fuel':'solar','perc':100}]
    process_event(engine, 'generation', mix)
    with engine.connect() as conn:
        result=conn.execute(select(generation.c.fuel, generation.c.percentage)).all()
    assert result==[('solar',100)]

def test_permanent_http_error_not_retried():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(400)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_json('/bad',client=client,sleep=lambda _:None)
    assert len(calls)==1

def test_captured_live_source_contract():
    import json
    from pathlib import Path
    fixture=json.loads((Path(__file__).parent/'fixtures'/'neso-captured.json').read_text())
    for event in fixture['events']:
        assert validate(event['kind'],event['payload'])

def test_concurrent_replay_is_single_claim(engine, intensity):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:process_event(engine,'intensity',intensity),range(8)))
    assert results.count('accepted')==1
    assert count(engine,raw_events)==count(engine,observations)==1
