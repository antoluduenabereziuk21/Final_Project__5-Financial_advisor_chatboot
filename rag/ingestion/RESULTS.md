# pre_procesing_2 results

Status: all 10 sample files processed end-to-end, including the two large
files (289/483 pages).

## Results per document

| File | form_type | fiscal_year | accounting_standard | front-matter cutoff (pages) | chunks (word_count) | numeric-dense chunks |
|---|---|---|---|---|---|---|
| NASDAQ_PRTK_2015.pdf | None (correctly -- see `pre_procesing_1/RESULTS.md` finding #1) | 2014 | None | 0 | 4 | 1 (25.0%) |
| NASDAQ_PIH_2016.pdf | 10-K | 2016 | US GAAP | 4 | 142 | 39 (27.5%) |
| NASDAQ_ACAD_2018.pdf | 10-K | 2018 | US GAAP | 6 | 175 | 15 (8.6%) |
| NASDAQ_GPP_2019.pdf | 10-K | 2019 | US GAAP | 3 | 204 | 33 (16.2%) |
| NASDAQ_AMRK_2021.pdf | 10-K | 2021 | US GAAP | 0 | 217 | 62 (28.6%) |
| NASDAQ_ABMD_2020.pdf | 10-K | 2020 | US GAAP | **30** | 161 | 20 (12.4%) |
| NASDAQ_PRTK_2018.pdf | 10-K | 2018 | US GAAP | 0 | 291 | 33 (11.3%) |
| NASDAQ_PODD_2016.pdf | 10-K | 2016 | US GAAP | 1 | 286 | 51 (17.8%) |
| NASDAQ_DDD_2021.pdf | 20-F (see finding below) | 2021 | IFRS | 0 | 433 | 60 (13.9%) |
| NASDAQ_VNET_2019.pdf | 20-F | 2019 | IFRS | 0 | 697 | 82 (11.8%) |

Full chunk text for every document (not just a sample) is in
`output/NASDAQ_*.json` under `chunks_word_count` -- written in full
specifically so chunks can be reviewed directly, per request.

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
the flag catches it.


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
