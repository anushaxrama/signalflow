from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from signalflow.pipeline import process_event, ingest
from signalflow.analytics import snapshot, scenario
from signalflow.api import create_app

def seed(engine, values, start=None):
    start=start or datetime(2026,10,1,tzinfo=timezone.utc)
    for i,value in enumerate(values):
        a=start+timedelta(minutes=i*30)
        process_event(engine,'intensity',{'from':a.isoformat(),'to':(a+timedelta(minutes=30)).isoformat(),'intensity':{'forecast':100,'actual':value,'index':'moderate'}})

def test_empty_state(engine):
    data=snapshot(engine)
    assert data['status']=='empty'
    assert data['metrics']['forecast_mae'] is None
    assert scenario(data,100,2,1.2)['available'] is False

def test_missing_actual_not_zero(engine):
    seed(engine,[None,110,90])
    data=snapshot(engine)
    assert data['metrics']['average_actual']==100
    assert data['metrics']['forecast_mae']==10
    assert data['metrics']['actual_coverage']==66.7

def test_no_lookahead_anomaly(engine):
    seed(engine,[100]*15+[200])
    data=snapshot(engine)
    assert len(data['anomalies'])==1
    assert data['anomalies'][0]['baseline']==100
    assert data['anomalies'][0]['z_score']==10

def test_historical_scenario_units(engine):
    seed(engine,[100,100,200,200])
    result=scenario(snapshot(engine),100,1,1.2)
    assert result['energy_kwh']==120
    assert result['best_kg']==12
    assert result['worst_kg']==24
    assert result['avoided_kg']==12

def test_scenario_excludes_gaps_and_missing(engine):
    seed(engine,[100,None,200])
    assert not scenario(snapshot(engine),100,1,1.2)['available']
    seed(engine,[100],datetime(2026,10,2,tzinfo=timezone.utc))
    assert not scenario(snapshot(engine),100,1,1.2)['available']

def test_freshness_uses_interval_not_fetch_time(engine):
    seed(engine,[100])
    assert snapshot(engine)['status']=='stale'

def test_mix_freshness(engine, mix):
    seed(engine,[100],datetime.now(timezone.utc)-timedelta(minutes=30))
    assert snapshot(engine)['status']=='stale'
    process_event(engine,'generation',mix)
    assert snapshot(engine)['status']=='stale'

def test_api_health_export_and_validation(engine):
    seed(engine,[110,None])
    with TestClient(create_app(engine)) as client:
        assert client.get('/health').json()['status']=='ok'
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert client.get('/api/overview?hours=0').status_code==422
        assert client.get('/api/scenario?duration_hours=0.7').status_code==422
        assert client.get('/api/scenario?power_kw=nan').status_code==422
        data=client.get('/api/overview').json()
        assert len(data['series'])==2
        csv=client.get('/api/export.csv')
        assert csv.status_code==200 and 'text/csv' in csv.headers['content-type']
        assert len(csv.text.splitlines())==3
        assert 'event_id' in csv.text
        assert client.get('/openapi.json').status_code==200

def test_window_keeps_time_gaps(engine):
    seed(engine,[100],datetime(2026,9,1,tzinfo=timezone.utc))
    seed(engine,[200],datetime(2026,10,1,tzinfo=timezone.utc))
    data=snapshot(engine,24)
    assert len(data['series'])==1

def test_metrics_and_case_study(engine):
    with TestClient(create_app(engine)) as client:
        response=client.get('/metrics')
        assert response.status_code==200
        assert 'signalflow_data_healthy 0' in response.text
        assert 'signalflow_interval_age_seconds' not in response.text
        assert client.get('/case-study').status_code==200
        assert 'frame-ancestors' in client.get('/').headers['content-security-policy']
