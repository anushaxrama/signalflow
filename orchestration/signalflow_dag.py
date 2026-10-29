"""Daily reconciliations complement the five-minute ingestion worker."""
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG('signalflow_reconcile', start_date=datetime(2026,1,1,tzinfo=timezone.utc),
         schedule='0 6 * * *', catchup=False, max_active_runs=1,
         default_args={'retries':2,'retry_delay':timedelta(minutes=5)},
         tags=['signalflow','data-quality']) as dag:
    ingest = BashOperator(task_id='reconcile_7_days', bash_command='cd /home/airflow/project && /home/airflow/pipeline-venv/bin/python -m signalflow.cli ingest --days 7')
    transform = BashOperator(task_id='build_warehouse', bash_command='cd /home/airflow/project/analytics && /home/airflow/dbt-venv/bin/dbt build --profiles-dir .')
    check = BashOperator(task_id='check_freshness', bash_command='cd /home/airflow/project && /home/airflow/pipeline-venv/bin/python -m signalflow.cli check')
    ingest >> transform >> check
