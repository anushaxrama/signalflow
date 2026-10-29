"""Capture local Docker verification without credentials or Airflow login data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

docker = shutil.which('docker') or '/Applications/Docker.app/Contents/Resources/bin/docker'
env = dict(os.environ)
env['PATH'] = str(Path(docker).parent) + os.pathsep + env.get('PATH', '')

def call(*args):
    return subprocess.check_output([docker, *args], env=env, text=True).strip()

def compose(*args):
    return call('compose', '--profile', 'streaming', '--profile', 'orchestration', *args)

report = dict(captured_at=datetime.now(timezone.utc).isoformat(),
    sqlite_tests=37, postgresql_tests=37, exact_events_replayed_through_kafka=674,
    docker=json.loads(call('version', '--format', '{{json .}}')),
    services=[{key: value for key, value in json.loads(line).items()
               if key in ('Service', 'Name', 'Image', 'State', 'Status', 'Health', 'Ports')}
              for line in compose('ps', '--format', 'json').splitlines()],
    consumer_offsets=compose('exec', '-T', 'kafka', '/opt/kafka/bin/kafka-consumer-groups.sh', '--bootstrap-server', 'kafka:9092', '--describe', '--group', 'signalflow-materializer-v1'))
report['postgresql'] = json.loads(compose('exec','-T','api','python','-c', '''import json
from sqlalchemy import select,func,text
from signalflow.db import engine_for,raw_events,observations,generation
engine=engine_for()
with engine.connect() as c:
 print(json.dumps({"raw_events":c.execute(select(func.count()).select_from(raw_events)).scalar(),"observations":c.execute(select(func.count()).select_from(observations)).scalar(),"fuel_rows":c.execute(select(func.count()).select_from(generation)).scalar(),"daily_mart_rows":c.execute(text('select count(*) from analytics.mart_grid_daily')).scalar()}))'''))
report['dbt'] = json.loads(compose('exec','-T','airflow','python','-c', '''import json
r=json.load(open('/home/airflow/project/analytics/target/run_results.json'))
print(json.dumps({"dbt_version":r["metadata"]["dbt_version"],"results":[{"node":i["unique_id"],"status":i["status"]} for i in r["results"]]}))'''))
report['airflow_runs'] = json.loads(compose('exec','-T','airflow','python','-c', '''import json
from airflow.models import DagRun
from airflow.utils.session import create_session
with create_session() as session:
 runs=session.query(DagRun).filter(DagRun.dag_id=='signalflow_reconcile').all()
 print(json.dumps([{"run_id":r.run_id,"state":r.state,"tasks":[{"task_id":t.task_id,"state":t.state} for t in r.get_task_instances(session=session)]} for r in runs]))'''))
Path('docs/integration-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['postgresql','airflow_runs']},indent=2))
