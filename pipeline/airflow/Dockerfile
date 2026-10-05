# Build context is the repository root (see docker-compose.yml).
FROM apache/airflow:2.10.5-python3.12

USER airflow

# dbt and DuckDB live in their own virtualenv so they never fight Airflow's pinned dependencies;
# the DAG calls them through this interpreter.
COPY pipeline/requirements.txt /tmp/pipeline-requirements.txt
RUN python -m venv /home/airflow/pipeline_venv \
    && /home/airflow/pipeline_venv/bin/pip install --no-cache-dir -r /tmp/pipeline-requirements.txt
