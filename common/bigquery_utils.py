
import os
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import NotFound


def _ensure_watermark_table(client: bigquery.Client, project_id: str, dataset_id: str, table_name: str) -> str:
    table_id = f"{project_id}.{dataset_id}.{table_name}"
    try:
        client.get_table(table_id)
        return table_id
    except NotFound:
        schema = [
            bigquery.SchemaField("pipeline_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("last_transaction_ts", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table)
        return table_id


def _update_transactions_watermark(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    watermark_table = os.getenv("BIGQUERY_WATERMARK_TABLE", "watermarks")
    table_id = _ensure_watermark_table(client, project_id, dataset_id, watermark_table)

    # Usa o MAX(transaction_ts) da tabela de destino como novo watermark global
    tx_table_id = f"{project_id}.{dataset_id}.transactions"
    query = f"SELECT MAX(transaction_ts) AS last_ts FROM `{tx_table_id}`"
    rows = list(client.query(query))
    if not rows or rows[0].last_ts is None:
        return

    last_ts = rows[0].last_ts
    rows_to_insert = [
        {
            "pipeline_name": "fintech_lakehouse",
            "last_transaction_ts": last_ts,
            "updated_at": datetime.now(timezone.utc),
        }
    ]
    client.insert_rows_json(table_id, rows_to_insert)


def load_parquet_directory_to_bigquery(local_dir: Path) -> None:
    project_id = os.environ["GCP_PROJECT_ID"]
    dataset_id = os.environ["BIGQUERY_DATASET"]
    bucket_name = os.environ["GCS_BUCKET"]
    prefix = os.getenv("GCS_PREFIX", "fintech-lakehouse").strip("/")

    client = bigquery.Client(project=project_id)

    for path in local_dir.rglob("*.parquet"):
        table_name = path.stem
        uri = f"gs://{bucket_name}/{prefix}/{path.name}"
        table_id = f"{project_id}.{dataset_id}.{table_name}"

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition="WRITE_APPEND",
        )

        load_job = client.load_table_from_uri(uri, table_id, job_config=job_config)
        load_job.result()

    _update_transactions_watermark(client, project_id, dataset_id)
