"""
Download the NASDAQ annual reports dataset from S3 into a local directory.

Credentials are read from environment variables (loaded from .env via
python-dotenv). Never hardcode AWS keys in this file or commit a .env file.

Usage:
    cp .env.example .env      # then fill in your own AWS credentials
    pip install -r requirements.txt
    python download_dataset.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import local

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "anyoneai-datasets")
PREFIX = os.getenv("S3_PREFIX", "nasdaq_annual_reports/")
LOCAL_DIR = os.getenv("LOCAL_DATA_DIR", "data/nasdaq_annual_reports")
MAX_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "32"))

_thread_local = local()


def list_objects(s3_client, bucket: str, prefix: str):
    """Yield all object keys under prefix, handling pagination (>1000 objects)."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"): 
                yield obj["Key"], obj["Size"]


def _make_session():
    return boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _s3_client():
    """One S3 client per thread (safe + connection reuse within the thread)."""
    client = getattr(_thread_local, "s3", None)
    if client is None:
        client = _make_session().client(
            "s3",
            config=Config(
                max_pool_connections=MAX_WORKERS,
                retries={"max_attempts": 5, "mode": "adaptive"},
            ),
        )
        _thread_local.s3 = client
    return client


def _local_path_for(key: str) -> str:
    relative_path = key[len(PREFIX) :] if key.startswith(PREFIX) else key
    return os.path.join(LOCAL_DIR, relative_path)


def _needs_download(key: str, size: int) -> bool:
    local_path = _local_path_for(key)
    return not (os.path.exists(local_path) and os.path.getsize(local_path) == size)


def _download_one(key: str) -> str:
    local_path = _local_path_for(key)
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    _s3_client().download_file(BUCKET, key, local_path)
    return key


def download_dataset():
    session = _make_session()
    s3 = session.client("s3")

    try:
        objects = list(list_objects(s3, BUCKET, PREFIX))
    except NoCredentialsError:
        sys.exit(
            "No AWS credentials found. Copy .env.example to .env and fill in "
            "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."
        )
    except ClientError as e:
        sys.exit(f"Failed to list s3://{BUCKET}/{PREFIX}: {e}")

    if not objects:
        sys.exit(f"No objects found under s3://{BUCKET}/{PREFIX} — check the prefix.")

    os.makedirs(LOCAL_DIR, exist_ok=True)

    pending = [(key, size) for key, size in objects if _needs_download(key, size)]
    skipped = len(objects) - len(pending)

    print(
        f"Found {len(objects)} objects under s3://{BUCKET}/{PREFIX} "
        f"→ {LOCAL_DIR}/ ({skipped} already present, {len(pending)} to download)"
    )
    print(f"Using {MAX_WORKERS} parallel workers")

    if not pending:
        print("Nothing to download.")
        return

    errors = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_download_one, key): key for key, _ in pending}
        with tqdm(total=len(pending), unit="file") as bar:
            for future in as_completed(futures):
                key = futures[future]
                try:
                    future.result()
                except Exception as e:
                    errors.append((key, e))
                bar.update(1)

    if errors:
        print(f"Failed {len(errors)}/{len(pending)} downloads. First errors:")
        for key, err in errors[:5]:
            print(f"  - {key}: {err}")
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    download_dataset()
