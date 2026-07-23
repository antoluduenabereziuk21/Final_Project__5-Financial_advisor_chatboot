"""
Parallel version of download_dataset.py.

The original script downloads objects sequentially, so total time is dominated
by per-request round-trip latency (TCP/TLS handshake + S3 API call), not
bandwidth. This version downloads with a thread pool, which matters a lot at
~10k objects: latency-bound sequential loops don't get faster with a better
internet connection, they get faster with concurrency.

boto3 clients are thread-safe for making calls (not for concurrent config
mutation), so a single client shared across a ThreadPoolExecutor is fine.

Usage: same as download_dataset.py (reads the same .env), just faster.
    python download_dataset_parallel.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "anyoneai-datasets")
PREFIX = os.getenv("S3_PREFIX", "nasdaq_annual_reports/")
LOCAL_DIR = os.getenv("LOCAL_DATA_DIR", "data/nasdaq_annual_reports")
MAX_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "16"))  # tune per your connection


def list_objects(s3_client, bucket: str, prefix: str):
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                yield obj["Key"], obj["Size"]


def _download_one(s3, key, size, prefix):
    relative_path = key[len(prefix):] if key.startswith(prefix) else key
    local_path = os.path.join(LOCAL_DIR, relative_path)
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

    if os.path.exists(local_path) and os.path.getsize(local_path) == size:
        return key, "skipped", None

    try:
        s3.download_file(BUCKET, key, local_path)
        return key, "ok", None
    except Exception as e:  # noqa: BLE001 - surface any failure, keep the pool alive
        return key, "failed", str(e)


def download_dataset():
    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    # Default botocore connection pool caps at 10 connections. With more
    # worker threads than pool slots, threads queue for a free connection
    # instead of running concurrently, silently erasing most of the benefit
    # of the thread pool. Pool size must be >= MAX_WORKERS.
    s3 = session.client("s3", config=Config(max_pool_connections=MAX_WORKERS))

    try:
        objects = list(list_objects(s3, BUCKET, PREFIX))
    except NoCredentialsError:
        sys.exit("No AWS credentials found. Fill in .env first.")
    except ClientError as e:
        sys.exit(f"Failed to list s3://{BUCKET}/{PREFIX}: {e}")

    if not objects:
        sys.exit(f"No objects found under s3://{BUCKET}/{PREFIX}.")

    os.makedirs(LOCAL_DIR, exist_ok=True)
    print(f"Downloading {len(objects)} objects with {MAX_WORKERS} workers -> {LOCAL_DIR}/")

    failures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_download_one, s3, key, size, PREFIX) for key, size in objects]
        for future in tqdm(as_completed(futures), total=len(futures), unit="file"):
            key, status, error = future.result()
            if status == "failed":
                failures.append((key, error))

    print(f"Done. {len(failures)} failed.")
    if failures:
        print("Failed keys (re-run this script to retry them, already-downloaded files are skipped):")
        for key, error in failures[:20]:
            print(f"  {key}: {error}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more")


if __name__ == "__main__":
    download_dataset()
