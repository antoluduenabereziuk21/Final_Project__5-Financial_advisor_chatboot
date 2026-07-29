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
        full_text, cleaned_pages, page_offsets, clean_report = cleaning.clean_from_raw_pages(raw_pages, pdf_path)
    else:
        full_text, cleaned_pages, page_offsets, clean_report = cleaning.clean_document(pdf_path)

    # cover_text for metadata detection uses the first 8 post-cutoff pages
    # REGARDLESS of page_type (cover/toc/body) -- form_type/fiscal_year/
    # accounting_standard detection needs the actual cover page text, which
    # is exactly the page excluded from chunking (see is_cover_page in
    # cleaning.py), so this must NOT be built from full_text.
    cover_text = "\n".join(p["text"] for p in cleaned_pages[:8])
    doc_meta = metadata.build_metadata(pdf_path, cover_text)

    wc_chunks = chunking.chunk_word_count(full_text, pdf_path)

    # chunk_index = "{company}_{filename_year}_{i}" -- a stable, human-readable
    # per-document position id (e.g. "1-800-flowerscom_2019_0"). Purpose: a
    # future retrieval layer doing neighbor expansion (pulling in the chunk
    # before/after a numeric-dense hit -- see the 2026-07-28 chunking-strategy
    # discussion) needs to reconstruct document order from chunk records alone,
    # which isn't guaranteed once chunks are loaded into a vector DB (list
    # order is not preserved metadata). Uses the FILENAME year, not the
    # cover-page-detected fiscal_year, because the filename year is always
    # present for every real corpus file (NASDAQ_TICKER_YEAR.pdf), whereas
    # cover-page detection can fail and return None -- an id must not contain
    # a literal "None". Only added to chunks_word_count, not
    # chunks_structure_sample -- the two are independent chunkings of the same
    # document with their own 0..N-1 numbering, so sharing one id scheme
    # across both would collide (wc_chunks[0] and struct_chunks[0] would both
    # be "..._0") if they were ever mixed into the same index; structure
    # chunks also aren't the saved/production chunk set (see RESULTS.md open
    # items), so there's no current consumer for an id on them.
    company = metadata.company_from_path(pdf_path)
    _, filename_year = metadata.ticker_and_filename_year(pdf_path)
    year_part = filename_year if filename_year is not None else "unk"
    for i, c in enumerate(wc_chunks):
        c["chunk_index"] = f"{company}_{year_part}_{i}"

    struct_chunks, struct_report = chunking.chunk_structure_then_word_count(full_text, pdf_path)
    # same boundaries struct_chunks used internally, exposed here so
    # word_count chunks -- which never ran structure detection themselves
    # -- can still be labeled with which Item/Part section they fall in.
    section_boundaries, _ = chunking.filtered_structure_boundaries(full_text)

    for group in (wc_chunks, struct_chunks):
        # Locate each chunk's REAL position in full_text via find(), not by
        # accumulating len(chunk_text) -- found by testing: Haystack's
        # split_overlap=50 makes consecutive chunks overlap by ~50 words,
        # so treating them as contiguous (offset += len(text)) drifts the
        # running offset forward faster than the real text position. On
        # PIH_2016 this put a known page-49 balance-sheet chunk on "page
        # 57" -- confirmed wrong by checking cleaning.py's own offset
        # lookup in isolation, which correctly resolved the same character
        # position to page 49. search_from advances by only 1 char per
        # chunk (not the full chunk length) specifically so the next,
        # overlapping chunk -- which can start WITHIN the previous chunk's
        # span -- is still found by find(), not skipped past.
        search_from = 0
        for c in group:
            start_offset = full_text.find(c["text"], search_from)
            if start_offset == -1:
                # shouldn't happen (chunk text is always a literal
                # substring of full_text) -- don't guess a page if it does
                c["page_start"] = None
                c["page_end"] = None
                if "detected_label" not in c:
                    c["detected_label"] = None
                continue
            end_offset = start_offset + len(c["text"])
            search_from = start_offset + 1
            c["page_start"] = cleaning.page_number_for_offset(page_offsets, start_offset)
            c["page_end"] = cleaning.page_number_for_offset(page_offsets, max(end_offset - 1, start_offset))
            if "detected_label" not in c:
                c["detected_label"] = chunking.label_for_offset(section_boundaries, start_offset)

    # per-chunk metadata on BOTH chunk groups -- pre_procesing_1 only did this
    # for struct_chunks (canonical_section needs an item_number, which only
    # those had a detected_label for), but every chunk now has a
    # detected_label (see above), so both groups get real item_number/
    # canonical_section values, not just structure_then_word_count chunks.
    for group in (wc_chunks, struct_chunks):
        for c in group:
            label = c.get("detected_label") or ""
            item_number = label.replace("Item ", "").strip() if label.startswith("Item") else None
            # part_number mirrors item_number's parsing exactly, just for the
            # "Part I"/"Part II" case detect_structure_boundaries also
            # produces (see chunking.py PART_RE) -- added so detected_label's
            # only remaining unique information (which Part a chunk falls
            # under) is available as a flat metadata field too, not just a
            # label string the caller has to parse itself.
            part_number = label.replace("Part ", "").strip() if label.startswith("Part") else None
            c["metadata"] = metadata.build_metadata(pdf_path, cover_text, item_number)
            c["metadata"]["part_number"] = part_number
            density, _ = metadata.numeric_density(c["text"])
            c["metadata"]["numeric_density"] = round(density, 4)
            # likely_numeric_dense deliberately dropped (2026-07-28): it was
            # just numeric_density >= 0.10 frozen at chunking time. Storing
            # only the float lets the retrieval layer apply (and tune) its
            # own threshold at query time without a full corpus reprocess --
            # see RESULTS.md.

            # page_start/page_end/source_file duplicated into metadata (not
            # just left at the top level of the chunk record) so citation
            # ("source_file, p.page_start") still works even if a downstream
            # ingestion step only persists the `metadata` dict into a vector
            # DB and drops top-level chunk fields -- confirmed this is a real
            # risk, not hypothetical, given metadata is the conventional
            # place a vector DB's citation/filter payload lives.
            c["metadata"]["page_start"] = c.get("page_start")
            c["metadata"]["page_end"] = c.get("page_end")
            c["metadata"]["source_file"] = c.get("source_file")

    elapsed = time.time() - t0

    n_dense_wc = sum(1 for c in wc_chunks if c["metadata"]["numeric_density"] >= metadata.NUMERIC_DENSITY_THRESHOLD)
    n_wc_with_item = sum(1 for c in wc_chunks if c["metadata"]["item_number"])

    result = {
        "pdf_path": pdf_path,
        "elapsed_seconds": round(elapsed, 1),
        "doc_metadata": doc_meta,
        "clean_report": clean_report,
        "n_chunks_word_count": len(wc_chunks),
        "n_chunks_structure": len(struct_chunks),
        "structure_report": struct_report,
        "n_chunks_numeric_dense": n_dense_wc,
        "n_chunks_word_count_with_item_number": n_wc_with_item,
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
          f"numeric_dense_chunks={result['n_chunks_numeric_dense']} "
          f"word_count_chunks_with_item_number={result['n_chunks_word_count_with_item_number']}")
    print(f"  cover_pages_excluded={result['clean_report']['n_cover_pages_excluded']} "
          f"toc_pages_excluded={result['clean_report']['n_toc_pages_excluded']}")
