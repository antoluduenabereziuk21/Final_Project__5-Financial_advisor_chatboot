"""
Profile the downloaded PDF corpus to make chunking/indexing decisions with
real numbers instead of guesses. Computes, per document and in aggregate:
pages, word count, and projected chunk counts under three candidate
chunking strategies (page-level, paragraph-level, 100-word sliding window
with 50-word overlap, per Wang et al. 2019).

This is deliberately cheap: it extracts text once per file and derives all
stats from that, rather than re-parsing per strategy.

Usage:
    pip install pypdf tqdm --break-system-packages
    python profile_corpus.py --dir data/nasdaq_annual_reports
    python profile_corpus.py --dir data/nasdaq_annual_reports --sample 200   # quick partial run

Output: prints an aggregate summary and writes per-file stats to
corpus_profile.csv for further analysis (e.g. plotting the length
distribution, since means hide skew and a handful of 300-page filings will
distort planning if you only look at the average).
"""
import argparse
import csv
import glob
import os
import re
import statistics
import sys

from pypdf import PdfReader
from tqdm import tqdm

WINDOW = 100
OVERLAP = 50


def sliding_window_chunks(word_count: int, window: int = WINDOW, overlap: int = OVERLAP) -> int:
    if word_count <= 0:
        return 0
    if word_count <= window:
        return 1
    step = window - overlap
    return 1 + -(-(word_count - window) // step)  # ceil division


def paragraph_count(text: str) -> int:
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return max(len(paragraphs), 1)


def profile_file(path: str):
    try:
        reader = PdfReader(path)
    except Exception as e:  # noqa: BLE001
        return {"path": path, "error": str(e)}

    pages = len(reader.pages)
    full_text = []
    for page in reader.pages:
        try:
            full_text.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            full_text.append("")
    text = "\n\n".join(full_text)
    words = len(text.split())

    return {
        "path": path,
        "pages": pages,
        "words": words,
        "paragraphs": paragraph_count(text),
        "sliding_window_chunks": sliding_window_chunks(words),
        "error": "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory containing downloaded PDFs")
    parser.add_argument("--sample", type=int, default=None, help="Only profile the first N files (useful mid-download)")
    parser.add_argument("--out", default="corpus_profile.csv")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "**", "*.pdf"), recursive=True))
    if not files:
        sys.exit(f"No PDFs found under {args.dir}")
    if args.sample:
        files = files[: args.sample]

    rows = []
    for path in tqdm(files, unit="file"):
        rows.append(profile_file(path))

    ok_rows = [r for r in rows if not r.get("error")]
    err_rows = [r for r in rows if r.get("error")]

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "pages", "words", "paragraphs", "sliding_window_chunks", "error"])
        writer.writeheader()
        writer.writerows(rows)

    if not ok_rows:
        sys.exit("All files failed to parse — check if these PDFs are scanned images (need OCR, not text extraction).")

    pages = [r["pages"] for r in ok_rows]
    words = [r["words"] for r in ok_rows]
    paragraphs = [r["paragraphs"] for r in ok_rows]
    swc = [r["sliding_window_chunks"] for r in ok_rows]

    def stats(vals):
        return f"total={sum(vals):,}  mean={statistics.mean(vals):.1f}  median={statistics.median(vals):.1f}  min={min(vals)}  max={max(vals)}"

    print(f"\nFiles profiled: {len(rows)}  (failed to parse: {len(err_rows)})")
    print(f"Pages:     {stats(pages)}")
    print(f"Words:     {stats(words)}")
    print("\nProjected chunk counts if you index the WHOLE corpus at this rate:")
    print(f"  Page-level chunks:            ~{sum(pages):,}")
    print(f"  Paragraph-level chunks:        ~{sum(paragraphs):,}  {stats(paragraphs)}")
    print(f"  Sliding window (100w/50w ovl): ~{sum(swc):,}  {stats(swc)}")

    if err_rows:
        print(f"\n{len(err_rows)} files failed text extraction (likely scanned/image-only PDFs needing OCR):")
        for r in err_rows[:10]:
            print(f"  {r['path']}: {r['error']}")

    print(f"\nPer-file details written to {args.out}")


if __name__ == "__main__":
    main()
