from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="fintech_lakehouse_30min",
    start_date=datetime(2025, 1, 1),
    schedule=timedelta(minutes=30),
    catchup=False,
    tags=["fintech", "lakehouse", "portfolio"],
):

    extract_postgres_to_gcs_parquet = BashOperator(
        task_id="extract_postgres_to_gcs_parquet",
        bash_command="python /opt/airflow/ingestion/postgres_to_gcs_parquet.py",
    )

    load_parquet_to_bigquery = BashOperator(
        task_id="load_parquet_to_bigquery",
        bash_command="python -c 'from common.bigquery_utils import load_parquet_directory_to_bigquery; import os; from pathlib import Path; load_parquet_directory_to_bigquery(Path(os.getenv("PARQUET_OUTPUT_DIR", "/opt/airflow/data/parquet")))'",
    )

    extract_postgres_to_gcs_parquet >> load_parquet_to_bigquery
