"""
Runs the full Stage 1->2 pipeline (cleaning -> chunking -> metadata) on one
document and assembles the acceptance-criteria report fields from
SPEC.md section 7. No table extraction stage -- see SPEC.md section 3/9.

Usage: python orchestrate.py <pdf_path> [raw_pages_cache]
raw_pages_cache: path to a JSON file of (page_number, text) tuples covering
the WHOLE document (see cleaning.extract_raw_pages + build_raw_pages_cache.py
for how large documents get this built across multiple batched calls -- the
same problem table_extraction.py's tables_cache solved in pre_procesing_1,
now needed because plain page.extract_text() alone measured at ~0.57s/page
on some files, e.g. NASDAQ_AMRK_2021.pdf, independent of tables).
If raw_pages_cache is not given or doesn't exist, extraction runs in a
single call via cleaning.clean_document() -- fine for documents short
enough to fit under this environment's 45s/call budget on their own.
"""
import json
import os
import sys
import time

import cleaning
import chunking
import metadata


def run_one(pdf_path: str, out_dir: str = "output", raw_pages_cache: str = None):
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    if raw_pages_cache and os.path.exists(raw_pages_cache):
        with open(raw_pages_cache) as f:
            raw_pages = [tuple(p) for p in json.load(f)]
        raw_pages.sort(key=lambda p: p[0])
        full_text, cleaned_pages, clean_report = cleaning.clean_from_raw_pages(raw_pages, pdf_path)
    else:
        full_text, cleaned_pages, clean_report = cleaning.clean_document(pdf_path)

    cover_text = "\n".join(cleaned_pages[:8])
    doc_meta = metadata.build_metadata(pdf_path, cover_text)

    wc_chunks = chunking.chunk_word_count(full_text, pdf_path)
    struct_chunks, struct_report = chunking.chunk_structure_then_word_count(full_text, pdf_path)

    # attach page ranges (approximate: proportional to character offset,
    # since Haystack's splitter doesn't track source page -- flagged as an
    # approximation, not exact, in the report)
    total_chars = max(len(full_text), 1)
    total_pages = clean_report["total_pages"] - clean_report["front_matter_cutoff_page"]
    for group in (wc_chunks, struct_chunks):
        offset = 0
        for c in group:
            start_frac = offset / total_chars
            end_frac = (offset + len(c["text"])) / total_chars
            c["page_start"] = clean_report["front_matter_cutoff_page"] + int(start_frac * total_pages) + 1
            c["page_end"] = clean_report["front_matter_cutoff_page"] + int(end_frac * total_pages) + 1
            offset += len(c["text"])

    # per-chunk metadata on BOTH chunk groups -- pre_procesing_1 only did this
    # for struct_chunks (canonical_section needs an item_number, which only
    # those have), but numeric_density needs no item_number and is just as
    # relevant to word_count chunks, so both groups get a metadata dict now.
    for group in (wc_chunks, struct_chunks):
        for c in group:
            label = c.get("detected_label", "")
            item_number = label.replace("Item ", "").strip() if label.startswith("Item") else None
            c["metadata"] = metadata.build_metadata(pdf_path, cover_text, item_number)
            density, likely_dense = metadata.numeric_density(c["text"])
            c["metadata"]["numeric_density"] = round(density, 4)
            c["metadata"]["likely_numeric_dense"] = likely_dense

    elapsed = time.time() - t0

    n_dense_wc = sum(1 for c in wc_chunks if c["metadata"]["likely_numeric_dense"])

    result = {
        "pdf_path": pdf_path,
        "elapsed_seconds": round(elapsed, 1),
        "doc_metadata": doc_meta,
        "clean_report": clean_report,
        "n_chunks_word_count": len(wc_chunks),
        "n_chunks_structure": len(struct_chunks),
        "structure_report": struct_report,
        "n_chunks_numeric_dense": n_dense_wc,
        "chunks_word_count": wc_chunks,
        "chunks_structure_sample": struct_chunks[:5],
    }

    safe_name = os.path.basename(pdf_path).replace(".pdf", "")
    out_path = os.path.join(out_dir, f"{safe_name}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    return result, out_path


if __name__ == "__main__":
    path = sys.argv[1]
    cache = sys.argv[2] if len(sys.argv) > 2 else None
    result, out_path = run_one(path, raw_pages_cache=cache)
    print(f"Wrote {out_path} in {result['elapsed_seconds']}s")
    print(f"  form_type={result['doc_metadata']['form_type']} fiscal_year={result['doc_metadata']['fiscal_year']} "
          f"accounting_standard={result['doc_metadata']['accounting_standard']}")
    print(f"  front_matter_cutoff_page={result['clean_report']['front_matter_cutoff_page']} "
          f"marker_found={result['clean_report']['front_matter_marker_found']}")
    print(f"  chunks(word_count)={result['n_chunks_word_count']} chunks(structure)={result['n_chunks_structure']} "
          f"numeric_dense_chunks={result['n_chunks_numeric_dense']}")
