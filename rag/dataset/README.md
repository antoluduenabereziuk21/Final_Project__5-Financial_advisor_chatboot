# Dataset access

The NASDAQ annual reports dataset lives in S3, not in this repo.
Two download scripts are available:

| Script | When to use |
|---|---|
| `download_dataset.py` | Sequential download — simple and predictable. Best for small batches or when concurrency is not needed. |
| `download_dataset_parallel.py` | **Faster** — downloads with a thread pool. Recommended for the full corpus (~10k objects), where latency-bound sequential downloads are significantly slower. |

## Prerequisites

1. Python 3.10+
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Setup

Copy the environment template and fill in your AWS credentials:

```bash
cp .env.example .env
```

Then edit `.env` with your own `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
Default values for the remaining variables should work as-is.

**Available environment variables:**

| Variable | Default | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | — | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | — | Your AWS secret key |
| `AWS_DEFAULT_REGION` | `us-east-1` | S3 bucket region |
| `S3_BUCKET` | `anyoneai-datasets` | S3 bucket name |
| `S3_PREFIX` | `nasdaq_annual_reports/` | Prefix inside the bucket |
| `LOCAL_DATA_DIR` | `data/nasdaq_annual_reports` | Local destination directory |
| `DOWNLOAD_WORKERS` | `16` | *(parallel only)* Number of concurrent download threads |

## Usage

### Sequential download

```bash
python download_dataset.py
```

### Parallel download (faster)

```bash
python download_dataset_parallel.py
```

Optionally tune the number of concurrent workers via environment variable:

```bash
# Use 32 concurrent threads
DOWNLOAD_WORKERS=32 python download_dataset_parallel.py
```

## Output

Data lands in `data/nasdaq_annual_reports/` (or the path set in `LOCAL_DATA_DIR`).
This directory is git-ignored.

Re-running either script only fetches missing or changed files (same-size files
are skipped), making re-runs after interruptions safe and fast.

## Security

Never commit `.env` or hardcode credentials in the Python scripts.
If a key is ever pasted in Slack, chat, or a ticket, treat it as compromised
and rotate it in IAM immediately.
