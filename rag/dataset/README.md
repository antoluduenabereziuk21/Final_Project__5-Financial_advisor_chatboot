# Dataset access

The NASDAQ annual reports dataset lives in S3, not in this repo. Pull it locally:

```bash
cp .env.example .env        # fill in your own AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
pip install -r requirements.txt
python download_dataset.py
```

Data lands in `data/nasdaq_annual_reports/` (git-ignored). Re-running the script only
fetches missing/changed files.

Never commit `.env` or hardcode credentials in `download_dataset.py`. If a key is ever
pasted in Slack/chat/ticket, treat it as compromised and rotate it in IAM immediately.
