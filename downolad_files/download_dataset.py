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

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "anyoneai-datasets")
PREFIX = os.getenv("S3_PREFIX", "nasdaq_annual_reports/")
LOCAL_DIR = os.getenv("LOCAL_DATA_DIR", "data/nasdaq_annual_reports")


def list_objects(s3_client, bucket: str, prefix: str):
    """Yield all object keys under prefix, handling pagination (>1000 objects)."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):  # skip folder placeholders
                yield obj["Key"], obj["Size"]


def download_dataset():
    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
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
    print(f"Downloading {len(objects)} objects from s3://{BUCKET}/{PREFIX} to {LOCAL_DIR}/")

    for key, size in tqdm(objects, unit="file"):
        relative_path = key[len(PREFIX):] if key.startswith(PREFIX) else key
        local_path = os.path.join(LOCAL_DIR, relative_path)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

        if os.path.exists(local_path) and os.path.getsize(local_path) == size:
            continue  # already downloaded, skip (idempotent re-runs)

        s3.download_file(BUCKET, key, local_path)

    print("Done.")


if __name__ == "__main__":
    download_dataset()
