"""
Batch runner over corpus_profile.csv's sample set (300 files), for running
locally -- no 45s/call constraint here, so no raw_pages_cache batching is
needed; each document just runs to completion in one call via
orchestrate.run_one() / cleaning.clean_document().

Parallel across processes (not threads -- pdfplumber parsing and the regex/
splitting work in cleaning/chunking are CPU-bound, so threads would still
serialize on the GIL; ProcessPoolExecutor actually uses multiple cores).
Each worker writes its own document's JSON (different filename per doc, so
no write conflicts); only the summary CSV row is sent back to the main
process, which does all the writing to batch_results.csv itself -- avoids
multiple processes fighting over one file.

Usage:
    python run_batch.py                        # all 300 files, cpu_count-1 workers
    python run_batch.py --limit 5               # smoke test on the first 5
    python run_batch.py --workers 4             # override worker count
    python run_batch.py --out-dir output_batch

Resumable: skips any file whose output JSON already exists, so re-running
after an interruption (or after fixing a bug on one bad file) picks up
where it left off instead of redoing completed work. Per-file errors are
caught and logged, not fatal -- one bad PDF (corrupt file, encoding the
regexes choke on, etc.) should not kill a 300-file run.
"""
import argparse
import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import orchestrate

RESULT_FIELDS = [
    "pdf_path", "status", "elapsed_seconds", "n_chunks_word_count",
    "form_type", "company_name_mismatch", "n_chunks_numeric_dense", "error",
]


def load_file_list(csv_path: str, corpus_root: str):
    """Returns (paths, preflagged_errors). preflagged_errors are rows the
    profiling step already flagged as broken (1 of 300: an "ACIA%20" file
    that throws "Stream has ended unexpectedly") -- skip these without
    even attempting them, rather than re-discovering the same failure."""
    paths = []
    preflagged_errors = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # corpus_profile.csv has mixed slash styles ("data/x\y\z.pdf")
            # from however it was generated -- normalize before joining.
            rel_path = row["path"].replace("\\", "/")
            full_path = os.path.join(corpus_root, rel_path)
            if row.get("error", "").strip():
                preflagged_errors.append((full_path, row["error"].strip()))
                continue
            paths.append(full_path)
    return paths, preflagged_errors


def load_file_list_from_mismatch(csv_path: str):
    """Source the file list from check_mismatch_only.py's output instead of
    corpus_profile.csv -- lets a batch be scoped to exactly the files
    already covered by a prior (cheap) mismatch check, e.g. running the
    full chunking pipeline over the ~3,300 files already checked rather
    than the full ~9,851-file corpus or the original 300-file sample.
    mismatch_check.csv's pdf_path values are already full relative paths
    (built from --scan-root, not corpus_profile.csv's `path` column), so no
    corpus_root join is needed here -- only slash normalization, since they
    can carry the same mixed-separator style seen elsewhere in this corpus.
    Note: company_name_mismatch is NOT reused from this file -- run_one()
    recomputes it fresh as a normal side effect of building doc_metadata
    during chunking (cheap; the expensive part is PDF extraction, which
    happens regardless), so there's no benefit to threading the old value
    through, and doing so would risk it going stale relative to whatever
    cleaning.py/metadata.py logic is current at chunking time."""
    paths = []
    preflagged_errors = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pdf_path = row["pdf_path"].replace("\\", "/")
            if row.get("error", "").strip():
                preflagged_errors.append((pdf_path, row["error"].strip()))
                continue
            paths.append(pdf_path)
    return paths, preflagged_errors


def process_one(pdf_path: str, out_dir: str) -> dict:
    """Runs inside a worker process. Must be a top-level function (not a
    closure) and re-import orchestrate itself -- ProcessPoolExecutor on
    Windows uses "spawn", so each worker starts a fresh Python interpreter
    that does not inherit the parent's already-imported modules; the
    `import orchestrate` at module scope above runs again in every worker,
    which is what makes this picklable/callable via submit() at all."""
    t0 = time.time()
    try:
        result, _ = orchestrate.run_one(pdf_path, out_dir=out_dir)
        elapsed = time.time() - t0
        meta = result["doc_metadata"]
        return {
            "pdf_path": pdf_path, "status": "ok", "elapsed_seconds": round(elapsed, 1),
            "n_chunks_word_count": result["n_chunks_word_count"],
            "form_type": meta["form_type"], "company_name_mismatch": meta["company_name_mismatch"],
            "n_chunks_numeric_dense": result["n_chunks_numeric_dense"], "error": "",
        }
    except Exception as e:  # noqa: BLE001 -- one bad file must not kill a 300-file batch
        elapsed = time.time() - t0
        return {
            "pdf_path": pdf_path, "status": "error", "elapsed_seconds": round(elapsed, 1),
            "n_chunks_word_count": "", "form_type": "", "company_name_mismatch": "",
            "n_chunks_numeric_dense": "", "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["profile", "mismatch"], default="profile",
                         help="'profile' (default) uses corpus_profile.csv's 300-file sample; "
                              "'mismatch' uses mismatch_check.csv's file list instead (e.g. to run "
                              "the full pipeline over files already covered by a prior mismatch check)")
    parser.add_argument("--csv", default="../downolad_files/corpus_profile.csv")
    parser.add_argument("--mismatch-csv", default="mismatch_check.csv")
    parser.add_argument("--corpus-root", default="../downolad_files")
    parser.add_argument("--out-dir", default="output_batch")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N files (smoke test)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                         help="parallel worker processes (default: cpu_count - 1, leaves 1 core free)")
    args = parser.parse_args()

    if args.source == "mismatch":
        files, preflagged_errors = load_file_list_from_mismatch(args.mismatch_csv)
    else:
        files, preflagged_errors = load_file_list(args.csv, args.corpus_root)
    if args.limit:
        files = files[: args.limit]

    os.makedirs(args.out_dir, exist_ok=True)
    results_path = os.path.join(args.out_dir, "batch_results.csv")
    write_header = not os.path.exists(results_path)
    results_f = open(results_path, "a", newline="", encoding="utf-8")
    writer = csv.writer(results_f)
    if write_header:
        writer.writerow(RESULT_FIELDS)
        results_f.flush()

    for pdf_path, err in preflagged_errors:
        print(f"[preflagged] skipping (profiling already flagged this file): {pdf_path} -- {err}")
        writer.writerow([pdf_path, "preflagged_error", "", "", "", "", "", err])
    if preflagged_errors:
        results_f.flush()

    # Resolve skip/missing up front (sequentially, cheap) so the pool only
    # ever gets handed files that actually need work.
    to_run = []
    n_skipped = n_missing = 0
    for pdf_path in files:
        safe_name = os.path.basename(pdf_path).replace(".pdf", "")
        out_json = os.path.join(args.out_dir, f"{safe_name}.json")
        if os.path.exists(out_json):
            n_skipped += 1
            continue
        if not os.path.exists(pdf_path):
            n_missing += 1
            print(f"MISSING FILE: {pdf_path}")
            writer.writerow([pdf_path, "missing_file", "", "", "", "", "", "file not found"])
            continue
        to_run.append(pdf_path)
    results_f.flush()

    print(f"{len(files)} total -- {n_skipped} already done, {n_missing} missing, "
          f"{len(to_run)} to process now, using {args.workers} parallel workers")

    t_batch_start = time.time()
    n_done = n_failed = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, pdf_path, args.out_dir): pdf_path for pdf_path in to_run}
        for i, future in enumerate(as_completed(futures), start=1):
            pdf_path = futures[future]
            safe_name = os.path.basename(pdf_path).replace(".pdf", "")
            r = future.result()
            if r["status"] == "ok":
                n_done += 1
                print(f"[{i}/{len(to_run)}] ok ({r['elapsed_seconds']}s): {safe_name} -- "
                      f"form={r['form_type']} chunks={r['n_chunks_word_count']} "
                      f"mismatch={r['company_name_mismatch']}")
            else:
                n_failed += 1
                print(f"[{i}/{len(to_run)}] FAILED ({r['elapsed_seconds']}s): {safe_name} -- {r['error']}")
            writer.writerow([r[field] for field in RESULT_FIELDS])
            results_f.flush()

    results_f.close()
    total_elapsed = time.time() - t_batch_start
    print()
    print(f"Batch done in {total_elapsed/60:.1f} min.")
    print(f"  ok={n_done}  failed={n_failed}  skipped={n_skipped}  missing={n_missing}  total={len(files)}")
    print(f"Per-file summary: {results_path}")


if __name__ == "__main__":
    main()
