import os
from pathlib import Path

from google.cloud import storage


def upload_directory_to_gcs(local_dir: Path) -> None:
    project_id = os.getenv("GCP_PROJECT_ID") or None
    bucket_name = os.environ["GCS_BUCKET"]
    prefix = os.getenv("GCS_PREFIX", "fintech-lakehouse").strip("/")

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    for path in local_dir.rglob("*.parquet"):
        rel_name = path.name
        blob_name = f"{prefix}/{rel_name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(path))
