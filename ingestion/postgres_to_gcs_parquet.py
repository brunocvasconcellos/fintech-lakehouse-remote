
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from common.gcs_utils import upload_directory_to_gcs
from google.cloud import bigquery


PARQUET_OUTPUT_DIR = Path(os.getenv("PARQUET_OUTPUT_DIR", "/opt/airflow/data/parquet"))
PARQUET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_POSTGRES_HOST = os.environ["SOURCE_POSTGRES_HOST"]
SOURCE_POSTGRES_PORT = os.environ.get("SOURCE_POSTGRES_PORT", "5432")
SOURCE_POSTGRES_DB = os.environ["SOURCE_POSTGRES_DB"]
SOURCE_POSTGRES_USER = os.environ["SOURCE_POSTGRES_USER"]
SOURCE_POSTGRES_PASSWORD = os.environ["SOURCE_POSTGRES_PASSWORD"]

engine = create_engine(
    f"postgresql+psycopg2://{SOURCE_POSTGRES_USER}:{SOURCE_POSTGRES_PASSWORD}"
    f"@{SOURCE_POSTGRES_HOST}:{SOURCE_POSTGRES_PORT}/{SOURCE_POSTGRES_DB}"
)


def get_last_transactions_watermark() -> datetime | None:
    """Lê o último transaction_ts carregado a partir de uma tabela de watermark no BigQuery.

    Se a tabela ainda não existir ou estiver vazia, retorna None, indicando carga full inicial.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    dataset_id = os.getenv("BIGQUERY_DATASET")
    if not project_id or not dataset_id:
        return None

    watermark_table = os.getenv("BIGQUERY_WATERMARK_TABLE", "watermarks")
    table_id = f"{project_id}.{dataset_id}.{watermark_table}"

    client = bigquery.Client(project=project_id)
    query = dedent(f"""
        SELECT last_transaction_ts
        FROM `{table_id}`
        WHERE pipeline_name = 'fintech_lakehouse'
        ORDER BY last_transaction_ts DESC
        LIMIT 1
    """)
    try:
        rows = list(client.query(query))
    except Exception:
        return None
    if not rows:
        return None
    return rows[0].last_transaction_ts


# Dimensões: carga simples (full) por enquanto
for name in ["customers", "accounts", "merchants"]:
    df = pd.read_sql(f"SELECT * FROM {name}", engine)
    df.to_parquet(PARQUET_OUTPUT_DIR / f"{name}.parquet", index=False)

# Fato transacional: carga incremental por transaction_ts
last_ts = get_last_transactions_watermark()
now_ts = datetime.now(timezone.utc)

if last_ts is None:
    tx_query = "SELECT * FROM transactions WHERE transaction_ts <= %(now_ts)s"
    params = {"now_ts": now_ts}
else:
    tx_query = (
        "SELECT * FROM transactions "
        "WHERE transaction_ts > %(last_ts)s "
        "AND transaction_ts <= %(now_ts)s"
    )
    params = {"last_ts": last_ts, "now_ts": now_ts}

transactions_df = pd.read_sql(tx_query, engine, params=params)
transactions_df.to_parquet(PARQUET_OUTPUT_DIR / "transactions.parquet", index=False)

upload_directory_to_gcs(PARQUET_OUTPUT_DIR)
