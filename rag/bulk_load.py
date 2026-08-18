"""
Bulk-load pre-embedded, pre-chunked parquet files (from
embeddings/colab_embed_chunks.py) into Postgres/pgvector.

Different from rag/app.py's /ingest endpoint: /ingest takes one PDF path,
re-runs the full extract -> clean -> chunk -> embed pipeline, and writes one
document. This script does none of that recomputation -- it reads files that
are already chunked AND already embedded (colab_embed_chunks.py's own timing
found GPU embedding ~30x faster than the CPU baseline, so redoing that work
here would be wasteful even if /ingest accepted pre-computed embeddings,
which it currently doesn't) and writes them straight into rag_chunks via
VectorRepository.insert_chunks_for_document() -- one documents upsert per
file, one batched executemany() for all of that file's chunks, not one
round-trip per chunk.

Each parquet row already carries everything needed (see
colab_embed_chunks.py's chunk_to_row()): text, the full metadata dict
(company/ticker/fiscal_year/form_type/accounting_standard/canonical_section/
company_name_mismatch/numeric_density), and the embedding vector. No join
against the original chunk JSON in output_batch/ is needed or performed here.

chunk_index caveat: the ingestion pipeline's own chunk_index field
(rag/ingestion/orchestrate.py) is a STRING like "1-800-flowerscom_2019_5",
not the INT rag_chunks.chunk_index expects. rag/app.py's /ingest endpoint
doesn't use that string either -- it assigns a fresh 0-indexed int from
enumerate() over the chunk list. This script does the same, using each row's
position within its own parquet file. That's safe because row order survives
end-to-end from chunking through embedding, and no rows are dropped
mid-document -- company_name_mismatch exclusion happens at the whole-document
level in colab_embed_chunks.py (a fully-excluded doc just never got a parquet
file written), not by dropping individual rows out of an otherwise-kept file.

Resumable: skips a file entirely if rag_chunks already has exactly as many
rows for its document as the file has (VectorRepository.get_document_chunk_count).
Per-file errors are caught and logged to --results-csv, not fatal -- one bad
parquet file must not kill a ~1,800-file load. Re-running after an
interruption picks up where it left off.

Usage:
    python bulk_load.py --input-dir /path/to/embeddings_output/all_minilm_l6_v2
    python bulk_load.py --input-dir ... --limit 5          # smoke test on 5 files
    python bulk_load.py --input-dir ... --results-csv out.csv

Run from the rag/ directory (same convention as app.py) so the bare
`from vector_store...` imports resolve:
    cd rag && python bulk_load.py --input-dir ...
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import time
from pathlib import Path

import pandas as pd

from vector_store.client import VectorDbClient
from vector_store.models import ChunkRecord
from vector_store.repository import VectorRepository

RESULT_FIELDS = ["file", "status", "n_chunks", "n_ticker_missing", "elapsed_seconds", "error"]


def _clean_int(value) -> int | None:
    """pandas represents a missing value in an otherwise-integer column as
    float NaN, not None/null, whenever that column has any nulls at all
    (numpy has no nullable-int NaN, only float does) -- confirmed real:
    AMEX_ATRS_2013.parquet chunk #166 had page_end come through as `nan`,
    which asyncpg correctly refuses to bind into an INT column. NaN here
    means the same thing None does (orchestrate.py's own fallback when a
    chunk's page couldn't be resolved via full_text.find()) -- convert it
    back rather than let it reach the DB as an unrepresentable float."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return int(value)


def _row_to_chunk_record(row: pd.Series, position: int) -> ChunkRecord:
    meta = row.get("metadata")
    if not isinstance(meta, dict):
        meta = dict(meta) if meta is not None else {}

    embedding = row.get("embedding")
    embedding = [float(v) for v in embedding] if embedding is not None else []

    fiscal_year = _clean_int(meta.get("fiscal_year")) or 0

    return ChunkRecord(
        content=row.get("text") or "",
        embedding=embedding,
        ticker=meta.get("ticker") or "",
        company=meta.get("company") or "",
        fiscal_year=fiscal_year,
        form_type=meta.get("form_type"),
        accounting_standard=meta.get("accounting_standard"),
        canonical_section=meta.get("canonical_section"),
        source_file=row.get("source_file") or "",
        page_start=_clean_int(row.get("page_start")),
        page_end=_clean_int(row.get("page_end")),
        numeric_density=meta.get("numeric_density"),
        chunk_index=position,  # see module docstring -- NOT the string chunk_index field
        company_name_mismatch=meta.get("company_name_mismatch"),
    )


async def _load_one(repo: VectorRepository, path: Path) -> dict:
    t0 = time.time()

    try:
        df = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001 -- one bad file must not kill the run
        return {
            "file": path.name, "status": "error", "n_chunks": 0, "n_ticker_missing": 0,
            "elapsed_seconds": round(time.time() - t0, 1), "error": f"read_parquet failed: {e}",
        }

    if df.empty:
        return {
            "file": path.name, "status": "empty", "n_chunks": 0, "n_ticker_missing": 0,
            "elapsed_seconds": round(time.time() - t0, 1), "error": "",
        }

    source_file = df.iloc[0].get("source_file") or ""
    existing = None
    if source_file:
        try:
            existing = await repo.get_document_chunk_count(source_file)
        except Exception:  # noqa: BLE001 -- lookup failure shouldn't block a retry, just re-attempt the load
            existing = None

    if existing is not None and existing == len(df):
        return {
            "file": path.name, "status": "skipped_already_loaded", "n_chunks": len(df),
            "n_ticker_missing": 0, "elapsed_seconds": round(time.time() - t0, 1), "error": "",
        }

    try:
        records = [_row_to_chunk_record(row, i) for i, (_, row) in enumerate(df.iterrows())]
        n_ticker_missing = sum(1 for r in records if not r.ticker)
        n_inserted = await repo.insert_chunks_for_document(records)
        return {
            "file": path.name, "status": "ok", "n_chunks": n_inserted,
            "n_ticker_missing": n_ticker_missing, "elapsed_seconds": round(time.time() - t0, 1), "error": "",
        }
    except Exception as e:  # noqa: BLE001 -- one bad file must not kill a ~1,800-file load
        return {
            "file": path.name, "status": "error", "n_chunks": 0, "n_ticker_missing": 0,
            "elapsed_seconds": round(time.time() - t0, 1), "error": str(e),
        }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, help="Directory of *.parquet files from colab_embed_chunks.py")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N files (smoke test)")
    parser.add_argument("--results-csv", default="bulk_load_results.csv")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    files = sorted(input_dir.glob("*.parquet"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise FileNotFoundError(f"No .parquet files found in {input_dir}")

    print(f"{len(files)} parquet file(s) to load from {input_dir}")

    client = await VectorDbClient().connect()
    repo = VectorRepository(client)

    write_header = not Path(args.results_csv).exists()
    n_ok = n_skipped = n_error = 0
    t_start = time.time()

    try:
        with open(args.results_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(RESULT_FIELDS)
                f.flush()

            for i, path in enumerate(files, start=1):
                r = await _load_one(repo, path)
                writer.writerow([r[field] for field in RESULT_FIELDS])
                f.flush()

                if r["status"] == "ok":
                    n_ok += 1
                    extra = f", {r['n_ticker_missing']} missing ticker" if r["n_ticker_missing"] else ""
                    print(f"[{i}/{len(files)}] ok ({r['elapsed_seconds']}s): {r['file']} -- {r['n_chunks']} chunks{extra}")
                elif r["status"] == "skipped_already_loaded":
                    n_skipped += 1
                    print(f"[{i}/{len(files)}] skip (already loaded): {r['file']}")
                else:
                    n_error += 1
                    print(f"[{i}/{len(files)}] {r['status'].upper()}: {r['file']} -- {r['error']}")
    finally:
        await client.close()

    total_min = (time.time() - t_start) / 60
    print()
    print(f"Done in {total_min:.1f} min. ok={n_ok} skipped={n_skipped} error={n_error} total={len(files)}")
    print(f"Per-file log: {args.results_csv}")


if __name__ == "__main__":
    asyncio.run(main())
