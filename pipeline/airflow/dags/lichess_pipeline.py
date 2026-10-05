"""Daily Lichess pipeline: ingest -> dbt build -> parity check -> export for the dashboard.

Every step is a command from this repository, so the same pipeline runs by hand
(see README) or under Airflow. The commands use the dedicated pipeline virtualenv
created in the Dockerfile.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

REPO = "/opt/airflow/repo"
PYTHON = os.environ.get("PIPELINE_PYTHON", "python")
DBT = os.environ.get("DBT_BIN", "dbt")

default_args = {"owner": "data", "retries": 1, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="lichess_pipeline",
    description="Lichess REST API -> DuckDB raw -> dbt marts -> SQLite for the dashboard",
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["lichess", "dbt"],
) as dag:

    # INGEST_MODE=api needs LICHESS_TOKEN; "fixture" loads the committed sample for offline runs.
    ingest = BashOperator(
        task_id="ingest",
        bash_command=(
            f'cd {REPO} && if [ "$INGEST_MODE" = "api" ]; then '
            f"{PYTHON} pipeline/ingest.py; "
            f"else {PYTHON} pipeline/ingest.py --from-file pipeline/fixtures/games_sample.ndjson; fi"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {REPO}/dbt/lichess && {DBT} build --profiles-dir .",
    )

    # A failing parity check means the dbt logic and the legacy pandas logic disagree.
    parity_check = BashOperator(
        task_id="parity_check",
        bash_command=f"cd {REPO} && {PYTHON} pipeline/check_parity.py --strict",
    )

    export_sqlite = BashOperator(
        task_id="export_to_sqlite",
        bash_command=f"cd {REPO} && {PYTHON} pipeline/export_to_sqlite.py",
    )

    ingest >> dbt_build >> parity_check >> export_sqlite
