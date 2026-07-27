# Preprocessing pipeline v2 — SPEC

Status: draft, experiment phase (same 10 sample files as `pre_procesing_1`, not the full corpus)
Owner: preprocessing workstream
Depends on: `downolad_files/data/nasdaq_annual_reports/` (downloaded dataset), `downolad_files/corpus_profile.csv` (corpus stats), and `pre_procesing_1/` (frozen — code copied from there as the starting point, and its `RESULTS.md` documents 5 real bugs already found and fixed in the shared cleaning/chunking/metadata logic; that knowledge carries over, it is not re-derived here).

## 1. Goal

Turn a raw 10-K / 20-F PDF into **one** thing a RAG pipeline can index: a sequence of clean, structure-aware text chunks with metadata, for the dense + lexical text indexes.

This is a scope reduction from `pre_procesing_1/SPEC.md`, which targeted two outputs (text chunks + a separate structured table index). See section 3 for why, and section 9 for what that change implies concretely.

Indexing (Elasticsearch, embeddings, DB) is out of scope here; see the architecture deck.

## 2. Sample set (unchanged)

Same 10 files as `pre_procesing_1/SPEC.md` section 2, spread across the real page-count distribution:

| Pages | Company | File |
|---|---|---|
| 3 | Paratek Pharmaceuticals | NASDAQ_PRTK_2015.pdf |
| 92 | 1347 Property Insurance Holdings | NASDAQ_PIH_2016.pdf |
| 106 | Acadia Pharmaceuticals | NASDAQ_ACAD_2018.pdf |
| 114 | Green Plains Partners LP | NASDAQ_GPP_2019.pdf |
| 121 | A-Mark Precious Metals | NASDAQ_AMRK_2021.pdf |
| 134 | Abiomed Inc | NASDAQ_ABMD_2020.pdf |
| 146 | Paratek Pharmaceuticals | NASDAQ_PRTK_2018.pdf |
| 193 | Insulet Corporation | NASDAQ_PODD_2016.pdf |
| 289 | 3D Systems Corp | NASDAQ_DDD_2021.pdf |
| 483 | 21Vianet Group Inc | NASDAQ_VNET_2019.pdf (20-F) |

4 of these (PRTK_2015, PIH_2016, ACAD_2018, GPP_2019) were already run end-to-end in `pre_procesing_1` — their `form_type`/`fiscal_year`/`accounting_standard`/chunk counts are known-good reference points (see `pre_procesing_1/RESULTS.md`), useful for confirming this version's chunking/metadata output hasn't regressed, independent of the table question.

## 3. Table extraction: explicitly deferred, not attempted here

`pre_procesing_1` spent significant effort on this (two extractors, four rounds of fixes: ruled-line detection, borderless fallback, false-positive filtering, a dedicated dot-leader parser) and still could not produce structured tables usable for a financial-advisor RAG — every geometric detection approach recovers the numeric grid but not its column headers, and even the best-performing approach (the dot-leader parser) fragments one logical financial statement into many disconnected pieces. Full rationale, evidence, and the decision are in `pre_procesing_1/RESULTS.md`, section "Final decision: table extraction deferred to v2" — not repeated here.

This version does not attempt table detection, extraction, or structuring at all. Table content is not treated as a distinct entity anywhere in this pipeline; see section 9 for what that implies for cleaning, chunking, and metadata.

## 4. Stage 1 — Cleaning

Runs on the **full page text, unmodified** — no bounding-box exclusion step. This is the one substantive behavior change from `pre_procesing_1/cleaning.py`: that version accepted a `table_bboxes_by_page` argument and dropped any word falling inside a table's bounding box before reconstructing page text. This version does not — whatever text pdfplumber extracts (including table regions, however irregularly spaced) flows through untouched by table logic.

Everything else carries over unchanged from `pre_procesing_1` (already validated against 4 real files, including 3 non-trivial bugs found and fixed — zero-space extraction, checkbox-glyph word splits, corpus contamination):

0. **Front-matter skip** — SEC-standardized cover-page marker detection (`FRONT_MATTER_RE` / `FRONT_MATTER_RE_NOSPACE`), pages before the match excluded from chunking, excluded range logged.
1. **Boilerplate/header-footer removal** — lines repeating across ≥60% of pages stripped.
2. **Dehyphenation** — line-wrap hyphens joined.
3. **Whitespace normalization** — collapsed spaces/tabs, normalized line endings. Note: this will visibly compress whatever column-gap whitespace existed in a table region (multiple spaces between a label and its number collapse to one) — expected and accepted, not a bug to fix here; see section 9.
4. **Encoding/ligature cleanup** — NFKC normalize, strip control characters.
5. **Glued-word de-gluing** (`deglue_words`, wordninja-based) — fixes the zero-space extraction defect found in `pre_procesing_1` (ACADIA 2018, ~92% of body text affected). Runs regardless of whether a region was originally a table or narrative text, same as before.
6. **Empty/near-empty document flag** — word count under 500 flagged for OCR review.

**Output:** cleaned full text per document, plus the same stripped-content report as before (line counts removed, dehyphenation count, glued-token count).

## 5. Stage 2 — Chunking (unchanged)

Same as `pre_procesing_1/SPEC.md` section 5 — both strategies carry over as-is, no logic change:

**Primary:** Haystack `DocumentSplitter`, `split_by="word"`, `split_length=350`, `split_overlap=50`.

**Structure-aware alternative:** Item/Part boundary detection (`ITEM_RE`/`PART_RE`, `\s*`-tolerant per the zero-space-extraction fix) then word-count splitting within each detected section, filtering boundaries under `MIN_SECTION_WORDS=30` to reject table-of-contents false matches (a heuristic, not a real TOC detector — same known limitation as before).

**Output per chunk** — identical to before minus `table_refs` (see section 9):
```
{
  "chunk_id": str,
  "text": str,
  "word_count": int,
  "source_file": str,
  "page_start": int,
  "page_end": int,
  "split_method": "word_count" | "structure_then_word_count"
}
```

## 6. Metadata schema (unchanged except table_refs removed)

Every chunk gets a metadata record populated from its own page/section context — same fields, same detection logic as `pre_procesing_1/SPEC.md` section 6, since none of this ever depended on table extraction in the first place:

| Field | Source | Notes |
|---|---|---|
| `company` | filename / folder name | unchanged |
| `ticker` | filename regex | unchanged |
| `form_type` | cover-page content | unchanged — `FORM_TYPE_RE`/`FORM_TYPE_RE_NOSPACE` |
| `fiscal_year` | filename + cover-page cross-check | unchanged |
| `part` | structure detection | unchanged |
| `item_number` | structure detection | unchanged |
| `canonical_section` | `canonical_sections.py` mapping | unchanged — this module has no table dependency |
| `accounting_standard` | deterministic (10-K) / cover-page checkbox (20-F) | unchanged — text-based, never used table extraction |
| `numeric_density` | computed from chunk text | float, fraction of whitespace-split tokens that are digit-dominant (see below) — new in this version |
| `likely_numeric_dense` | thresholded `numeric_density` | bool, `numeric_density >= 0.10` — new in this version |

Removed: `table_refs` (chunks) and the entire "tables get independent metadata records" design. See section 9.

**`numeric_density` / `likely_numeric_dense` — rationale and validation.** With no table index (section 9), a chunk that used to be a table row is retrieved the same way as any narrative chunk — dense/lexical similarity search, which is weak at surfacing "the chunk with the number in it" specifically. This field doesn't try to detect tables; it flags chunks likely to contain figures at all, so retrieval/reranking can boost them for number-seeking queries. A token counts as numeric if, after stripping `$,%()-.` and whitespace, what's left is ≥60% digits (same digit-dominance test used in `pre_procesing_1` to separate real table cells from prose, re-applied per-token to running chunk text rather than per-cell).

Validated on real chunk output (not page-level text, which was noisier — a page can mix narrative and a small table; the 350-word chunk is the right granularity since that's what retrieval actually sees) across 4 sample docs:

| Doc | Chunks | Median density | Max density | Flagged @ 0.10 |
|---|---|---|---|---|
| PIH_2016 | 142 | 0.05 | 0.32 | 27.5% |
| ACAD_2018 | 175 | 0.01 | 0.27 | 8.6% |
| GPP_2019 | 204 | 0.02 | 0.40 | 16.2% |
| PRTK_2015 | 4 | 0.08 | 0.12 | — (too few chunks to threshold meaningfully) |

Each doc shows the same shape — a low-density majority with a distinct high-density tail — and the flagged fraction tracks how table-dense the filing actually is (PIH, already flagged as an unusually table-heavy small-cap filing, flags 3x more chunks than ACAD). Known limitation, stated plainly rather than glossed over: this also flags numeric-heavy narrative (MD&A prose full of dollar figures) and structured non-table content (exhibit indices, legal reference lists) — confirmed by inspecting chunks right at the 0.10 boundary. For this pipeline's purpose (surface chunks likely to answer a number-seeking query) that's acceptable, arguably even correct — but it should not be described anywhere downstream as "table detection."

## 7. Acceptance criteria for this experiment

- Cleaning: confirm boilerplate-repeat detection still catches real repeated headers on the 483-page file without stripping real content.
- Chunking: compare word-count-only vs. structure-aware chunk boundaries side by side on the 3-page and 483-page files, same as before.
- Metadata: every chunk from all 10 files has non-null `company`, `ticker`, `form_type`, `fiscal_year`. `part`/`item_number`/`canonical_section` non-null rate reported honestly.
- Front-matter skip: report excluded page range per document, manually confirm on 2-3 files.
- `accounting_standard`: confirm the 20-F sample (NASDAQ_VNET_2019.pdf) resolves from its cover-page checkbox, not a default.
- **No silent data loss (new, replaces the table-extraction checks from v1):** pick 2-3 known figures from a table in a source PDF (e.g. PIH_2016's total assets, `$90,849` on p.49) and confirm the number appears in the text of *some* chunk from that document. This is the check that matters now that tables aren't excluded or structured — it verifies the decision in section 3 didn't quietly turn into data loss rather than a scope cut.
- `numeric_density`/`likely_numeric_dense`: confirm the flagged fraction per document is in a plausible range (not 0%, not near 100%) and spot-check 2-3 flagged chunks per document actually contain numbers, not a false trigger.

## 8. Explicitly out of scope here

Same as `pre_procesing_1/SPEC.md` section 8 (embedding, indexing, the LLM generator, the database decision, GAAP/IFRS numeric normalization) **plus, newly: table extraction, table structuring, and a separate tables index** — deferred to a v2 preprocessing effort per section 3, not attempted in this folder at all.

## 9. What dropping table preprocessing implies, concretely

This section exists because the change is easy to understate as "just don't run `table_extraction.py`" — it touches several other things:

- **`table_refs` is gone**, from the chunk schema (section 5) and from the metadata design (section 6). There is no `table_id` to reference, because nothing produces one.
- **No separate table index.** The original architecture (RAG deck, `pre_procesing_1/SPEC.md` goal) planned a tables index for exact-figure questions, populated independently of the text index. That data source does not exist in this version. Anything downstream planning to query "the tables index" needs to know it has no v1 data to query — this is a real gap in the product, not just a preprocessing detail, and should be flagged wherever indexing/retrieval gets designed next.
- **Figures live inside ordinary chunks now, not a structured store.** A number that used to be a table cell is now just a word inside a 350-word chunk, retrieved the same way any other text is (embedding/BM25 similarity), and interpreted by the LLM from raw, irregularly-spaced text at generation time — not looked up by row/column. This is weaker for precise figure retrieval than a working table index would have been, and is the direct cost of the section 3 decision, accepted as a v1 tradeoff.
- **`cleaning.py` changes behavior, not just loses an argument.** `pre_procesing_1`'s version actively deleted table-region words from the text (the whole point of the bbox-exclusion mechanism). This version keeps them. That's a behavior change with a consequence worth stating plainly: chunks that land on a table-heavy page will look visibly worse (collapsed whitespace where columns used to be, numbers running together with labels) than chunks from narrative pages. Accepted per section 7's new acceptance criterion — presence over cleanliness.
- **`orchestrate.py` gets simpler**, not just smaller: no `table_extraction` import, no `tables_cache` parameter, no per-table metadata loop, no `n_tables`/`tables_sample` output fields, no bbox-passing into `cleaning.clean_document`.
- **`requirements.txt` drops table-only dependencies**: `camelot-py`, `opencv-python-headless`, `ghostscript`. `pdfplumber` stays — still needed for page/word text extraction, just not `find_tables()`.
- **Unaffected, worth stating explicitly so it isn't assumed lost too:** `form_type`, `fiscal_year`, `accounting_standard`, and `canonical_section` detection never depended on table extraction — all of it reads cover-page or section-header text directly. None of that logic changes in this version.
- **Considered and deliberately not included:** using the cheap, reasonably-precise primary pdfplumber ruled-line detector *only* as a chunk-boundary signal (keep a detected table's text span intact rather than letting the 350-word window slice through it, without attempting to structure its contents) was discussed as a lightweight middle ground. Not included here since the instruction for this version is no table preprocessing at all — noted here so it isn't lost if a future iteration wants a low-cost partial improvement before committing to full ML-based structure recognition.
