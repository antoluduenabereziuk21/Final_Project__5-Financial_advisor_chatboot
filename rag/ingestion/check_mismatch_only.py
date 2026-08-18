"""
Standalone, cheap company_name_mismatch check -- does NOT run the full
pipeline (chunking, full-document text extraction). Only extracts the
first MAX_PAGES pages of each PDF, which is enough to reach the real SEC
cover page even past a glossy front-matter section (confirmed sufficient
with a wide margin on the worst case seen: acxiom-corporation's
front-matter cutoff lands at page 10 of 30 scanned; do not lower
--max-pages much below 30, confirmed 5 is not enough even on an ordinary
filing -- 1-800-flowers' front matter alone runs past 5 pages).

By default scans the ENTIRE corpus on disk (data/nasdaq_annual_reports/,
confirmed 9,851 PDFs), not just the 300-file corpus_profile.csv sample --
use --source csv to restrict to that sample instead.

Resumable (skips rows already in mismatch_check.csv) -- safe to re-run
after an interruption.

Usage:
    python check_mismatch_only.py --workers 6              # whole corpus (~9,851 files)
    python check_mismatch_only.py --source csv --workers 6  # just the 300-file sample
"""
import argparse
import csv
import glob
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import cleaning
import metadata

MAX_PAGES = 30  # see check_mismatch_only.py module docstring / CLI --max-pages:
# 30 was picked because acxiom-corporation's real SEC cover page sits behind a
# 10-page glossy front-matter section -- anything much lower risks silently
# losing coverage on exactly the tricky documents this check exists to catch
# (front-matter cutoff won't be found -> registrant_name=None -> "unchecked",
# not "checked and fine"). Override via --max-pages if you want to trade
# coverage for speed anyway.


def process_one(pdf_path, max_pages):
    if not os.path.exists(pdf_path):
        return [pdf_path, "", "", "", "file not found"]
    try:
        raw_pages = cleaning.extract_raw_pages(pdf_path, page_start=1, page_end=max_pages)
        _, cleaned_pages, _, _ = cleaning.clean_from_raw_pages(raw_pages, pdf_path)
        cover_text = "\n".join(p["text"] for p in cleaned_pages[:8])
        company = metadata.company_from_path(pdf_path)
        name, mismatch = metadata.check_company_name_mismatch(company, cover_text)
        return [pdf_path, company, name or "", mismatch, ""]
    except Exception as e:  # noqa: BLE001 -- one bad file must not kill the run
        return [pdf_path, "", "", "", str(e)]


def load_paths_from_csv(csv_path, corpus_root):
    paths = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("error", "").strip():
                continue
            rel = row["path"].replace("\\", "/")
            paths.append(os.path.join(corpus_root, rel))
    return paths


def load_paths_from_disk(scan_root):
    # recursive glob -- every *.pdf under scan_root, regardless of whether
    # it's in corpus_profile.csv's 300-file sample.
    pattern = os.path.join(scan_root, "**", "*.pdf")
    return sorted(glob.glob(pattern, recursive=True))


def already_done(out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row["pdf_path"])
    return done


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["disk", "csv"], default="disk",
                         help="'disk' (default) scans every PDF under --scan-root (whole corpus, "
                              "~9,851 files); 'csv' restricts to corpus_profile.csv's 300-file sample")
    parser.add_argument("--scan-root", default="../downolad_files/data/nasdaq_annual_reports",
                         help="base directory to recursively scan for *.pdf when --source disk")
    parser.add_argument("--csv", default="../downolad_files/corpus_profile.csv")
    parser.add_argument("--corpus-root", default="../downolad_files")
    parser.add_argument("--out", default="mismatch_check.csv")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES,
                         help="pages scanned per PDF to find the cover page (default 30; "
                              "lower is faster but risks missing documents with long front matter)")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N files (smoke test)")
    args = parser.parse_args()

    if args.source == "disk":
        paths = load_paths_from_disk(args.scan_root)
    else:
        paths = load_paths_from_csv(args.csv, args.corpus_root)
    if args.limit:
        paths = paths[: args.limit]
    done = already_done(args.out)
    todo = [p for p in paths if p not in done]

    write_header = not os.path.exists(args.out)
    out_f = open(args.out, "a", newline="", encoding="utf-8")
    writer = csv.writer(out_f)
    if write_header:
        writer.writerow(["pdf_path", "company", "registrant_name", "company_name_mismatch", "error"])
        out_f.flush()

    print(f"{len(paths)} total, {len(done)} already done, {len(todo)} to process with {args.workers} workers")

    n_processed = 0
    if todo:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(process_one, p, args.max_pages) for p in todo]
            for i, future in enumerate(as_completed(futures), start=1):
                row = future.result()
                writer.writerow(row)
                out_f.flush()
                n_processed += 1
                if i % 200 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)} done")

    out_f.close()
    print(f"Finished. Processed {n_processed} this run. Results: {args.out}")


if __name__ == "__main__":
    main()
