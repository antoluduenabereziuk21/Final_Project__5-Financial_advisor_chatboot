# RAG backend — local setup (database + embeddings)

For teammates who need to stand up the vector DB and load the pre-embedded corpus. Full table/column reference: `docs/database_schema.md`.

## 1. Stand up the database

Prereqs: Docker Desktop installed and running. Run from repo root.

```bash
./rag/init_db.sh
```

Starts `rag_vector_db` (Postgres 16 + pgvector) and `pgadmin` (`docker/docker-compose.yml`), applies `rag/vector_store/init_db.sql`. Idempotent, safe to re-run — schema changes to an already-existing table are applied via explicit `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` lines in `init_db.sql`, since `CREATE TABLE IF NOT EXISTS` alone silently no-ops once the table exists (confirmed real when `company_name_mismatch` was added).

Default connection: `postgresql://ml_engineer:ml_password_2026@localhost:5432/financial_rag_vectors` (override in `rag/.env`; full var list in `docs/database_schema.md`).

Verify the schema landed:

```bash
docker exec -i rag_vector_db psql -U ml_engineer -d financial_rag_vectors -c "\d rag_chunks"
```

`company_name_mismatch` (boolean, nullable) should be the last column.

pgAdmin (optional GUI): `http://localhost:8080`, login with `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`. When registering the server, use host `rag_vector_db` (the container name on the Docker network) — not `localhost`.

## 2. Python environment for the loader

```bash
cd rag
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.11+. (Previously documented as 3.9+ -- that's wrong: `backend/app/services/chat_service.py` imports `datetime.UTC`, added in 3.11, and several files rely on bare `X | None` type syntax that only evaluates at runtime on 3.10+. Confirmed by actually hitting `ImportError: cannot import name 'UTC' from 'datetime'` on a 3.9 venv.)

## 3. Where to put the embeddings (`output_embeding`)

`rag/bulk_load.py` reads a directory of `*.parquet` files, one per source document, from `colab_embed_chunks.py`'s output — not something this repo generates itself. Each row is self-contained (text, full metadata, embedding vector); no join against anything else is needed.

Standard local path (gitignored — do not commit parquet data):

```
rag/embeddings/output/all_minilm_l6_v2/
```

Drop the downloaded parquet files there.

**Open question, not yet resolved:** this folder currently exists only on fran's machine. It is not committed to git and has no shared distribution point (drive / bucket / release asset) yet. Until that's set up, anyone else running this step needs the files sent to them directly.

## 4. Load

Smoke test first:

```bash
python bulk_load.py --input-dir embeddings/output/all_minilm_l6_v2 --limit 5
```

Check `bulk_load_results.csv` (gitignored, per-run log) — status column should read `ok`. Then run the full load, same command without `--limit`. The load is resumable: interrupting and re-running skips any document whose chunk count in `rag_chunks` already matches its parquet file.

## 5. Verify

```bash
docker exec -i rag_vector_db psql -U ml_engineer -d financial_rag_vectors -c "SELECT COUNT(*) FROM documents;"
docker exec -i rag_vector_db psql -U ml_engineer -d financial_rag_vectors -c "SELECT COUNT(*) FROM rag_chunks;"
```

Reference values for the full corpus (confirmed 2026-08-10): 1,774 documents, 403,864 chunks.

Do not trust pgAdmin's dashboard "Live tuples" figure for this check — it's `pg_stat_user_tables.n_live_tup`, a stale autovacuum estimate, not a real count. Use `COUNT(*)`.
