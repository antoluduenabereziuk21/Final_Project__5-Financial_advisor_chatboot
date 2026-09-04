# rag/ingestion results

Status: current pipeline code (`cleaning.py`, `chunking.py`, `metadata.py`,
`orchestrate.py`, `run_batch.py`, `canonical_sections.py`, `check_mismatch_only.py`)
verified line-by-line on 2026-08-10 against the corpus batch actually in use.
This file previously described itself as `pre_procesing_2 results` and
contained two claims that are now confirmed stale -- corrected in the status
section below, original findings kept below that since they're still
accurate. Read this section first; it supersedes the "Open items" section
at the bottom where the two disagree.

## Status update (2026-08-10)

**The 300-doc `output_batch/` claim is stale -- a real batch already exists
and is current-schema.** The old "Open items" section below says
`output_batch/` predates `chunk_index` and needs a full rebuild. That was
true when written. It no longer is: a batch of **1,819 chunked JSON files**
(not 300) exists (currently archived outside this repo at
`final_project/arquive/pre_procesing_2/output_batch/`, `.gitignore`'d, never
committed) and is confirmed to be **post-fix schema** -- inspected a sample
chunk directly (`NASDAQ_AACG_2018.json`): has `chunk_index`, has
`part_number` in `metadata`, does **not** have `likely_numeric_dense`.
That's an exact field-for-field match to what the current code in this
folder produces (verified by reading `orchestrate.py` lines ~49-144 against
the sample). This is the batch actually being used downstream for
embeddings, per direct instruction -- treat `output_batch/` (1,819 files) as
the current production chunk set, not the 300-file `output_batch` described
in this file's original write-up.

**Provenance gap, not fully resolved.** `output_batch/batch_results.csv`
inside that batch logs exactly 300 rows, but the directory holds 1,819 JSON
files -- ~1,519 files exist with no corresponding log row. `run_batch.py`
is resumable and appends to the same results CSV across `--source profile`
and `--source mismatch` runs, so this gap isn't explained by normal
resumed-run behavior. Possible causes not yet checked: a truncated/
overwritten CSV, direct `orchestrate.py` calls bypassing `run_batch.py`, or
files merged in from a separate run's output directory. Don't treat
`batch_results.csv` as a complete manifest of what's in `output_batch/`
until this is resolved.

**Non-NASDAQ files present, silently degraded.** 1,813 of the 1,819 files
are `NASDAQ_*`; 3 are `AMEX_*` (ATRS, three fiscal years), 1 is a TSX file,
1 is NYSE. `metadata.TICKER_RE` only matches a `NASDAQ_` prefix, so for
these 5 files `ticker` and `fiscal_year_from_filename` come back `None`
silently (no error, no flag) -- small blast radius (5/1,819) but real, and
it means the corpus isn't purely NASDAQ despite the project's stated scope.

**`mismatch_check.csv` coverage claim was also stale -- corrected here.**
The "Batch runner" section below cites "~3,324 files at time of writing,
~33% of the corpus" for `mismatch_check.csv`. Checked directly (2026-08-10):
the original `mismatch_check.csv` has 299 data rows; a separate file,
`mismatch_check - Copy.csv` (same location, `pre_procesing_2/`, both now
archived), has 2,036 data rows -- **20.7% of the 9,851-file corpus**, not
33%. The two files share **zero overlapping `pdf_path` values** -- they are
not sequential snapshots of one resumable run, they're two separate,
differently-scoped invocations of `check_mismatch_only.py` (one likely
`--source csv` restricted to the 300-file profiling sample, the other a
default whole-corpus scan that stopped partway through, alphabetically
early). `mismatch_check - Copy.csv` has 59 confirmed `company_name_mismatch
= True` rows, 437 `None`/unchecked rows, and 7 rows with a real extraction
`error`. Schema (`pdf_path,company,registrant_name,company_name_mismatch,error`)
matches what `run_batch.py --source mismatch` expects exactly -- no code
change needed to point at it once the file itself is back in this folder
(it currently is not; see repo-orientation discussion for where it moved).

## Results per document (after the 2026-07-26 fix round)

| File | form_type | company_name_mismatch | cover/TOC pages excluded | chunks (word_count) | numeric-dense | chunks with item_number |
|---|---|---|---|---|---|---|
| NASDAQ_PRTK_2015.pdf | None (correctly) | None (no cover page found) | 0 / 0 | 4 | 1 (25.0%) | 0 |
| NASDAQ_PIH_2016.pdf | 10-K | False | 1 / 4 | 135 | 36 (26.7%) | 133 (98.5%) |
| NASDAQ_ACAD_2018.pdf | 10-K | False | 1 / 1 | 173 | 14 (8.1%) | 171 (98.8%) |
| NASDAQ_GPP_2019.pdf | 10-K | False | 1 / 0 | 202 | 32 (15.8%) | 201 (99.5%) |
| NASDAQ_AMRK_2021.pdf | 10-K | False | 1 / 0 | 215 | 59 (27.4%) | 214 (99.5%) |
| NASDAQ_ABMD_2020.pdf | 10-K | False | 1 / 1 | 159 | 18 (11.3%) | 156 (98.1%) |
| NASDAQ_PRTK_2018.pdf | 10-K | False | 1 / 0 | 289 | 35 (12.1%) | 285 (98.6%) |
| NASDAQ_PODD_2016.pdf | 10-K | False | 1 / 4 | 283 | 55 (19.4%) | 282 (99.6%) |
| NASDAQ_DDD_2021.pdf | 20-F | **True** (see finding below) | 1 / 0 | 432 | 60 (13.9%) | 425 (98.4%) |
| NASDAQ_VNET_2019.pdf | 20-F | False | 1 / 0 | 696 | 86 (12.4%) | 694 (99.7%) |

Full chunk text for every document (not just a sample) is in
`output/NASDAQ_*.json` under `chunks_word_count` -- written in full
specifically so chunks can be reviewed directly, per request.

## Fix round (2026-07-26): 4 issues raised from reviewing the chunks, all fixed

Raised after reviewing actual chunk output, in order:

1. **Cover page and table-of-contents were being chunked as regular
   content.** Fixed: `cleaning.py` now identifies the cover page (the page
   `find_front_matter_cutoff` actually matched on) and any table-of-
   contents page (`is_toc_page` -- a page with several
   "label........pagenumber" dot-leader lines, the same convention real
   financial data rows use but with exactly one trailing value instead of
   2+) and excludes both from `full_text`/chunking entirely, while still
   keeping their text available for cover-page metadata detection. Real
   bug found while fixing this: the first version excluded "page index 0"
   unconditionally as "the cover page" even on documents where
   `front_matter_marker_found` was False (no real cover page ever
   detected) -- confirmed on PRTK_2015, which lost its only substantive
   page to this before the fix (`marker_found` must gate the exclusion,
   not just page position).

2. **Dot-leader fill ("......") was eating chunk space.** Fixed:
   `cleaning.collapse_dot_leaders` replaces any run of 4+ dots (space-
   tolerant) with a fixed `" ... "`, applied to every page during cleaning.
   Label/value association is untouched -- only the filler shrinks.

3. **Chunk page numbers didn't match the source PDF.** Root cause: the
   proportional character-offset estimate assumed uniform character
   density per page, which doesn't hold (a dense page vs. a sparse one).
   Fixed with **exact** tracking: `cleaning.py` now returns `page_offsets`
   (real per-page character spans within `full_text`), and
   `cleaning.page_number_for_offset` does a direct lookup. Second real bug
   found while fixing this: the first version located each chunk's
   position by accumulating `len(chunk_text)`, which assumes chunks are
   contiguous -- they're not, `split_overlap=50` makes consecutive chunks
   share ~50 words, so the running offset drifted forward faster than the
   real text position. On PIH_2016 this put a known page-49 balance-sheet
   chunk on "page 57". Fixed by locating each chunk via `full_text.find()`
   instead of arithmetic -- confirmed the known figure now lands on the
   correct page (49-50).

4. **`item_number`/`canonical_section` were null on every `word_count`
   chunk.** Root cause (see task #10's diagnosis): these fields were only
   ever computed for `structure_then_word_count` chunks, which is a
   different, separately-generated chunk set from `chunks_word_count` --
   the one saved in full and the one actually being reviewed. Fixed:
   `chunking.filtered_structure_boundaries` (the same Item/Part boundary
   detection `structure_then_word_count` already used internally) is now
   exposed and run once per document; every `word_count` chunk gets
   labeled by which section its real text position falls into via
   `chunking.label_for_offset`. Result: `item_number` populated on
   98-100% of word_count chunks across all 8 real 10-K/20-F documents in
   this sample (up from 0%).

Also answered directly (was asked as a question, not a "fix"): **no
automated company-name-vs-folder check existed** before this round -- the
DDD_2021/36Kr finding below was found by manual inspection. Built one:
`metadata.detect_registrant_name` extracts the real company name from the
cover page's "(Exact Name of Registrant as Specified in Its Charter)"
line, and `check_company_name_mismatch` token-compares it against the
folder-derived name (corporate suffixes and punctuation stripped, so
"3D Systems Corporation" vs "3d-systems-corp" still matches on shared
tokens). Now runs automatically as part of `build_metadata` --
`company_name_mismatch` in every chunk's metadata. Confirmed correct on
both known cases: `False` for ACADIA (real match) and `True` for
NASDAQ_DDD_2021.pdf (the 36Kr case). Returns `None`, not `False`, when no
registrant name could be found at all (PRTK_2015) -- an unchecked document
should not silently read as "checked, no problem."

## Finding: NASDAQ_DDD_2021.pdf is not 3D Systems Corp

Checked directly against the source PDF, not assumed from the pipeline's
own output: the file at
`downolad_files/data/nasdaq_annual_reports/3d-systems-corp/NASDAQ_DDD_2021.pdf`
is a genuine SEC Form 20-F, but for **36Kr Holdings Inc.** -- a Beijing-
based media/tech company incorporated in the Cayman Islands, reporting in
Renminbi. Nothing about 3D Systems Corp (the Delaware-incorporated NASDAQ:
DDD 3D-printing company this file is supposed to be) appears in it.

This is a more severe version of `pre_procesing_1` finding #1 (the
PRTK_2015 Form 12b-25 misclassification). That case was the *right*
company with the *wrong* document type. This is the *wrong company
entirely*, filed under another company's ticker/folder in the source
dataset. The pipeline's `form_type`/`accounting_standard` detection did
exactly what it should here -- it read the actual cover page rather than
trusting the filename, and correctly reported `20-F`/`IFRS`, which is what
exposed the mismatch. Implication, same as finding #1's: this kind of
folder/filename-vs-content mismatch is a real, confirmed defect in the
downloaded corpus, not a hypothetical edge case -- a full-corpus run should
cross-check company name from cover-page text against the folder name and
flag mismatches, not just trust the S3 folder structure.

## Numeric-density metadata: working as validated

`likely_numeric_dense` flags 8.6%-28.6% of chunks per document (excluding
the 3-page PRTK_2015 notice, too few chunks to be meaningful). This tracks
with which documents were already known to be more table/figure-heavy
(PIH_2016 and AMRK_2021, the two most numeric-dense here, were also the
two where `pre_procesing_1` found the most real financial-statement
content). Spot-check: PIH_2016's total assets figure (`$90,849`, from the
balance sheet on p.49 of the source PDF) appears in a chunk from
`NASDAQ_PIH_2016.json`, and that chunk is correctly flagged
`likely_numeric_dense: true` (density 0.211) -- confirms the section 7
"no silent data loss" criterion for at least this one figure, and confirms
the flag catches it. Note: `likely_numeric_dense` was later dropped from
the schema (see 2026-07-28 audit below) in favor of storing the raw
`numeric_density` float -- the finding above is still valid, it just now
reads as `numeric_density: 0.211 >= NUMERIC_DENSITY_THRESHOLD (0.10)`.

## Cover-page boilerplate-stripping bug (2026-07-28)

Found while investigating `company_name_mismatch` false positives at 300-doc
scale: `cleaning.py`'s running-header/footer stripper (`strip_boilerplate`,
triggered when a line repeats on >=60% of a document's body pages) was being
applied to the cover page too. A company's own name is very commonly used as
a running header throughout the rest of the filing -- exactly what makes it
look like boilerplate -- so it was getting deleted from the one page where
it's load-bearing content, not noise. Confirmed real cases: `Blackbaud,
Inc.` (blackbaud-inc), `BLOOMIN' BRANDS, INC.` (bloomin-brands-inc) were
each the *only* line flagged as boilerplate, and stripping it left
`REGISTRANT_NAME_RE` capturing the line above instead ("Commission file
number: ..."), which then read as a false mismatch. Fixed (confirmed live
in `cleaning.py` as of 2026-08-10): the cover page is now exempted from
boilerplate stripping. A second, unrelated failure mode was found alongside
it and given its own guard rather than "fixed":
biotelemetry-inc/NASDAQ_BEAT_2017.pdf's registrant name is genuinely absent
from pdfplumber's raw cover-page text (checked directly, not a cleaning.py
artifact -- likely a corrupted font on that specific PDF), so
`_looks_like_company_name` now explicitly rejects a captured name starting
with "Commission file number" and reports `None` (unchecked) rather than a
wrong name -- no text-extraction strategy recovers text that was never
extracted.

## Chunking strategy: page-based chunking considered and rejected (2026-07-28)

Question raised: since tables are no longer extracted separately and now
live mixed into ordinary text (per the v1 table-extraction deferral
decision above), would chunking one PDF page = one chunk keep tables intact
and reduce embedding count, instead of splitting on a fixed word count?

Checked against real data from this project rather than deciding from
theory:

- **Table/numeric-block fragmentation is real and common.** Across the
  300-doc `output_batch` run available at the time: 16.6% of all
  `chunks_word_count` chunks are `likely_numeric_dense`, and 61.7% of those
  have a numeric-dense chunk immediately adjacent to them -- strong
  evidence that most numeric/table content currently gets split across a
  chunk boundary by the plain word-count splitter.
- **Page-based chunking would not reliably fix that.** Measured real body
  page word counts (1-800-flowerscom, blackbaud-inc samples): min 0, max
  1124, stdev 310, vs. the current word-count chunker's output: mean 376,
  stdev only 21.6. Page-based chunking would trade a small, consistent
  chunk-size distribution for a wildly inconsistent one -- near-empty
  chunks next to 1000+ word chunks mixing multiple unrelated topics into
  one embedding, which hurts retrieval precision. It also doesn't
  guarantee table integrity: SEC financial-statement tables routinely
  continue across multiple physical pages ("(continued)" convention), so a
  page boundary is not a reliably safe cut point either.
- **"Fewer embeddings, faster response" does not hold as stated.** Fewer,
  larger chunks means fewer stored embeddings, but more tokens per
  retrieved chunk passed to the LLM at query time -- slower and more
  costly generation per query, not faster, unless retrieval `k` is also
  reduced (which then risks missing content).

Decision: page-based chunking rejected. Two alternatives were compared --
(a) a chunking-time fix (extend a chunk past its word-count cutoff when the
cutoff would land inside a numeric-dense run) vs. (b) a retrieval-time fix
(always pull in the chunk before/after a `likely_numeric_dense` hit at
query time -- the "sentence-window" / "auto-merging retrieval" pattern).
(b) was chosen: it only pays a cost when a dense chunk is actually
retrieved rather than for every table whether queried or not, needs no
table-boundary detection logic to get wrong, can be tuned later without
reprocessing the corpus, and additionally recovers cases a chunking-time
fix cannot -- e.g. a table's header row and data rows landing in different
chunks purely from an ordinary word-count cut, with neither chunk alone
scoring well against a label-based query. Retrieval-time expansion is out
of scope for this preprocessing stage, but it requires each chunk to know
its own position in its source document, which is not otherwise
reconstructable once chunks are loaded into a vector DB -- hence the
`chunk_index` field below.

## chunk_index field (2026-07-28)

Added `chunk_index` (format `"{company}_{filename_year}_{i}"`, e.g.
`"1-800-flowerscom_2019_5"`) to every `chunks_word_count` record, 0-indexed
per document. Purpose: a future retrieval layer doing neighbor expansion
(pulling in the chunk before/after a `likely_numeric_dense` hit, so a
table's header and data rows can be reunited at query time even when they
landed in different chunks -- see the chunking-strategy discussion,
2026-07-28) needs to reconstruct each chunk's position within its source
document from the chunk record alone, which isn't guaranteed once chunks
are loaded into a vector DB (list order is not preserved metadata). Uses
the FILENAME year (always present, `NASDAQ_TICKER_YEAR.pdf`), not the
cover-page-detected `fiscal_year` (can be `None` on detection failure,
which would put a literal "None" in the id). Verified on
NASDAQ_FLWS_2019.pdf (single-document test, not a full batch run): 93
chunks, ids `1-800-flowerscom_2019_0` through `_92`, all unique. Deliberately
NOT added to `chunks_structure_sample` -- it's a separately-numbered 0..N-1
chunking of the same document, so sharing one id scheme would collide
(`wc_chunks[0]` and `struct_chunks[0]` would both be `..._0`) if the two
were ever mixed into one index, and structure chunks aren't the saved/
production chunk set (see Open items below).

**Status as of 2026-08-10: this has now been run at scale.** The 1,819-file
`output_batch/` in current use has `chunk_index` populated on every
`chunks_word_count` record -- confirmed by direct inspection, not assumed.
See the status section at the top of this file.

## Metadata schema audit (2026-07-28)

User audited every field in `chunk["metadata"]` against how it'll actually
be used in the downstream RAG pipeline (LLM input vs. SQL filter vs.
citation vs. nothing). Decisions:

- **`page_start`, `page_end`, `source_file`** copied into `metadata` (were
  only at the top level of the chunk record before). Reasoning: these are
  what a citation ("according to `source_file`, p.`page_start`") needs to
  be constructed from, and a downstream ingestion step that only persists
  `metadata` into a vector DB's payload -- the conventional pattern -- would
  otherwise silently lose them. Top-level copies are kept too (no reason to
  remove them).
- **`likely_numeric_dense` dropped.** It was just
  `numeric_density >= 0.10` frozen at chunking time. Storing only the float
  lets a retrieval layer apply, and later tune, its own threshold at query
  time (e.g. for the neighbor-expansion strategy in the section above)
  without a full corpus reprocess. `n_chunks_numeric_dense` in the report
  now derives from `numeric_density >= metadata.NUMERIC_DENSITY_THRESHOLD`
  directly instead of reading the old boolean.
- **`part_number` added**, parsed from `detected_label` the same way
  `item_number` already was ("Part II" -> `"II"`). Makes `detected_label`
  fully redundant for `Item`-labeled chunks (kept anyway, cheap and
  harmless) but was NOT redundant before this for `Part`-labeled ones.
  Caveat found while verifying: on a real test document (168 chunks,
  blackbaud-inc/NASDAQ_BLKB_2018.pdf), `part_number` populated on 0 chunks
  even though `item_number` populated on 167 -- in practice a "PART II"
  heading is immediately followed by its first "Item" heading with
  essentially no body text between them, so almost every chunk gets the
  more specific Item label instead. Implemented correctly; just don't
  expect it to be commonly populated.
- **`company` vs `registrant_name` kept as two separate fields, not
  merged.** They're deliberately different sources being cross-checked
  against each other (`company_name_mismatch`'s whole purpose) -- merging
  them would delete the ability to detect exactly the corpus defects found
  earlier (36Kr filed under 3d-systems-corp, Plantronics filed under
  acxiom-corporation). Roles clarified: `company` (folder-derived, already
  lowercase/hyphenated) is the SQL filter/join key; `registrant_name`
  (verbatim cover-page text) is for citation/display, not filtering, since
  its capitalization/punctuation isn't consistent across filers and years.
  Not stripping formatting from `registrant_name` -- that's supposed to be
  the accurate, citable legal name, and normalizing it would defeat that
  purpose. `company` is already the normalized field; no third field added.
  Filtering policy: `company` is safe to filter on when
  `company_name_mismatch` is `False` or `None`; `True` means don't trust
  the folder-derived name for that document.
- **Ticker format checked against real data, not assumed.** Length
  distribution across all 9,851 files on disk: 1 char (8), 2 chars (155), 3
  chars (671), 4 chars (8,677), 5 chars (132). 4 chars dominates but "always
  4-5" is wrong -- 834 files (8.6%) have 1-3 character tickers. A
  fixed-width SQL column would truncate/reject those; use `VARCHAR`.
  Ticker's own extraction logic (`ticker_and_filename_year` in
  metadata.py) has no other fixed-length assumption anywhere in the
  codebase -- checked, nothing else to correct. Left as-is per instruction.
  Also found, unrelated to tickers directly: some filenames carry a stray
  UUID suffix (duplicate-download artifact, e.g.
  `NASDAQ_FDEF_2016_4d6da4153f8b49878e764a44d917f26f.pdf`) and some use
  `.PDF` instead of `.pdf` -- neither breaks the current ticker regex, but
  the `.PDF` case would make a case-sensitive glob (e.g.
  `check_mismatch_only.py`'s `*.pdf` pattern) silently skip those files on
  a non-Windows filesystem. Separately confirmed 2026-08-10: this same
  `NASDAQ_`-only assumption also means non-NASDAQ files (AMEX/TSX/NYSE,
  5 confirmed in the current `output_batch`) get `ticker=None` -- see
  status section above.

Verified via single-document tests (NASDAQ_FLWS_2019.pdf,
NASDAQ_BLKB_2018.pdf), not a batch run, per instruction.

## Batch runner: `--source mismatch` option (2026-07-28)

`run_batch.py` can now source its file list from `mismatch_check.csv`
instead of `corpus_profile.csv`'s 300-file sample (`--source mismatch`),
scoping a full-pipeline chunking run to exactly the files a prior
`check_mismatch_only.py` pass already covered. Files `check_mismatch_only.py`
already flagged as broken (its own `error` column, e.g. "Unexpected EOF")
are skipped the same way `corpus_profile.csv`'s preflagged errors already
were -- never sent through the actual chunking pipeline, just logged as
`preflagged_error` in `batch_results.csv`. `company_name_mismatch` is NOT
reused from `mismatch_check.csv` -- `run_one()` recomputes it fresh as a
normal side effect of chunking (cheap; PDF extraction is the real cost and
happens regardless), avoiding any risk of the value going stale relative to
whatever cleaning.py/metadata.py logic is current when the full batch
actually runs. Verified with `--limit 2`: preflagged rows correctly
skipped, both real files processed correctly (chunk counts match prior
known values for these files).

**Coverage number corrected 2026-08-10**: the "~3,324 files, ~33% of
corpus" estimate below was never actually verified against the real file
and is wrong. Checked directly: `mismatch_check.csv` itself only has 299
rows. A separately-named file, `mismatch_check - Copy.csv`, has 2,036 rows
(20.7% of the 9,851-file corpus) and is what's actually intended as the
`--source mismatch` file list going forward (see status section at top).
The two files do not overlap at all -- they're separate runs, not
snapshots of one growing file. The 1.0%-corruption-rate figure below was
computed against the wrong denominator as a result; not re-verified here.

## Open items

- Cross-check company name (cover-page text) against folder name across a
  larger sample to size how common the DDD_2021/36Kr mismatch is in the
  full corpus.
- `numeric_density`/`likely_numeric_dense` threshold (0.10) was calibrated
  on 4 documents' word_count chunks in this experiment -- worth re-checking
  against a larger sample before treating it as final, same caveat as the
  zero-space-defect prevalence question from `pre_procesing_1`.
- Structure-aware chunking (`chunks_structure_sample`) was run and counted
  for every document but only sampled (first 5) in the output JSON, unlike
  `chunks_word_count` which is saved in full -- revisit if the full
  structure-chunk set needs review too.
- ~~`output_batch/` (300-doc run) predates both the cover-page
  boilerplate-stripping fix and the `chunk_index` field -- needs a full
  rebuild~~ **RESOLVED 2026-08-10, see status section at top**: a
  1,819-file, post-fix `output_batch/` exists and is in production use.
  The provenance gap (1,819 files vs. 300 logged rows) and the
  `mismatch_check - Copy.csv` coverage/overlap findings above are the new
  open items in its place.
- `corpus_profile.csv` (300-file random sample) is being deprecated as
  `run_batch.py`'s file-list source in favor of `mismatch_check - Copy.csv`
  (2,036 files, 20.7% of corpus) -- per direct instruction, 2026-08-10.
  Not yet done: `mismatch_check - Copy.csv` needs to physically be back in
  this folder (or `run_batch.py`'s `--mismatch-csv` default needs to point
  at wherever it lives) before `--source mismatch` can actually use it.
  `corpus_profile.csv` and `rag/dataset/profile_corpus.py` still exist and
  still work for corpus-wide profiling stats (ticker length distribution,
  etc.) -- "eliminate" has not yet been scoped to mean delete the file vs.
  just stop using it as the default batch source.
