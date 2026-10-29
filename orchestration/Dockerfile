FROM apache/airflow:2.10.5-python3.12
USER airflow
RUN python -m venv /home/airflow/dbt-venv
RUN /home/airflow/dbt-venv/bin/pip install --no-cache-dir 'dbt-core>=1.10,<2' 'dbt-postgres>=1.9,<2'
# The pipeline has its own environment to avoid Airflow 2's SQLAlchemy 1 constraint.
RUN python -m venv /home/airflow/pipeline-venv
COPY --chown=airflow:root requirements.lock /tmp/pipeline-requirements.lock
RUN /home/airflow/pipeline-venv/bin/pip install --no-cache-dir -r /tmp/pipeline-requirements.lock
COPY --chown=airflow:root . /home/airflow/project
ENV PYTHONPATH=/home/airflow/project
ENV AIRFLOW__CORE__DAGS_FOLDER=/home/airflow/project/orchestration
