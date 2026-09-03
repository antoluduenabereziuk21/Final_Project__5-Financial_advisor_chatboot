# RAG pipeline assessment — 2026-09-03

Supersedes the earlier version, which opened with "finish the Supabase load."
That was true but minor. The load being half-finished was masking a defect
that would have invalidated the evaluation regardless of corpus size.

Everything below is measured. Sections 1–5 are deterministic findings from the
database, the pipeline outputs and the installed packages. Section 6 is the
RAGAS run: 50 scored questions, judge `gemini-3.5-flash-lite`.

---

## 1. Headline: filtered retrieval never returned anything

`rag_chunks` carries an HNSW index (`vector_cosine_ops`) with
`hnsw.ef_search = 40`. An ANN index is scanned **before** the WHERE clause: it
returns ~40 nearest neighbours across all 403,864 chunks, and the
company/fiscal-year filter is applied to those 40 survivors.

Amgen FY2021 owns 276 chunks. The chance any appear in the global top 40 for
*"What was AMGN's research and development expense in fiscal 2021?"* is nil.
The query returned **zero rows** while 276 matching rows sat untouched.

| query | rows |
|---|---|
| `WHERE company='amgen-inc' AND fiscal_year=2021` | **276** |
| same, plus `ORDER BY embedding <=> $1::vector LIMIT 5` | **0** |

An ORDER BY cannot remove rows. An ANN index scan can. Downstream, zero
sources became `entity_not_found` — the user saw a confident, false claim that
the filing does not exist.

**The unfiltered path was no better, in the opposite direction.** Same
questions, no filter:

| question | top hit |
|---|---|
| AMGN R&D expense FY2021 | `bio-path-holdings-inc` |
| Aemetis R&D expense FY2017 | `agm-group-holdings-inc` |
| aTyr Pharma net loss FY2020 | `bassett-furniture-industries-inc` |

Both paths were broken. The system appeared to work only because entity
resolution almost never fired against the truncated Supabase index (21 of 70
questions), so nearly every query took the unfiltered path and produced a
fluent answer grounded in an unrelated company's filing.

**Fix.** When filters are present, evaluate them first in a `MATERIALIZED`
CTE, then run KNN over that subset — exact nearest-neighbour rather than
approximate, which is both more correct and cheap, since a company+year filter
leaves a few hundred rows. Unfiltered queries still use HNSW.

Supporting index added (`idx_rag_chunks_company_year`); the prefilter was
seq-scanning 403,864 rows per query. Note `idx_rag_chunks_ticker_year` — the
only pre-existing index for filtering — is on `(ticker, fiscal_year)`, and
`EntityResolver` deliberately never emits a ticker filter. It has never been
used and cannot be.

**`rag/sql/match_rag_chunks.sql` still carries the identical defect.** The
hosted Supabase path silently returns nothing for every filtered query.

---

## 2. Corpus and index state

Active index is **local Docker pgvector**, not Supabase.

| | local (active) | Supabase (hosted) |
|---|---|---|
| documents | 1,774 | 842 |
| chunks | 403,864 | — |
| distinct tickers | **444** | 206 |
| ticker range | AACG–ZYXI | **AACG–ATRS** |

The Supabase load stopped mid-alphabet at ATRS — an interrupted bulk load, not
a filter, and not completable on the free tier. Eval and demo both run locally.

Embedding dimension 384 (matches the schema); zero NULL tickers; 13.2% of
chunks have unverified company attribution; `canonical_section` NULL on 20.6%
(the section classifier was never finished).

**Year coverage is 2017–2021.** FY2019 peaks at 397 companies; FY2022 has 104,
FY2023 has 1. A financial-advisor demo will be asked about recent years and
the corpus largely cannot answer.

**~1.5% of chunks are unreadable, and far more by volume.** 5,924 chunks
contain `(cid:` — the marker a PDF extractor emits for a glyph it cannot map.
The top 25 affected filings alone hold ~130 MB of text. These are the same
documents as the 1,544 chunks over 20,000 characters: garbled text has no
sentence structure, so the splitter finds no boundaries and emits the whole
document as one chunk. The largest is **2,483,577 characters** (~600k tokens,
past any context window). A 112,893-char chunk produced a 92,564-token request
against a 200,000/day cap, reproducibly, from one off-topic question.

Mitigated at query time by a 20,000-char cap in `search_similar`
(`RAG_MAX_CHUNK_CHARS`). The cap is not arbitrary: the distribution is
bimodal, with 772 chunks between 4,005 and 19,771, nothing until 20,276, then
1,544 above. Verified not to change any scored row's retrieval.

---

## 3. Generation-layer defects found and fixed

All confirmed in the pipeline runs, all in `rag/llm/generator.py`.

**Output language.** 52 of 70 English questions were answered in Spanish. The
prompt was Spanish; the corpus is English SEC filings, so every figure was
being translated out of its source text. Now English-only.

**The confidence flag gated nothing.** `_llm_generate` never branched on
`flag`; the `low_confidence` refusal lived only in the no-provider dev path.
In production the flag was computed correctly and ignored. Now each flag
injects a prompt instruction *and* a code-enforced banner.

**Refusals were reported as successes.** 45 of 70 rows returned "the context
does not contain this" while carrying `confidence_flag = "ok"`. `ok` fired on
45 refusals and 12 real answers. The prompt now emits a machine-checkable
`NOT_IN_CONTEXT` sentinel and the flag downgrades to `no_answer_in_context`.

**The subjective gate was Spanish-keyword-only and ran too late.** All three
English `subjective_gate_bypass` rows ("Should I invest in Apple?") scored
`ok` and got a full generated answer. Markers are now bilingual, and the check
runs *before* the empty-retrieval check — a compliance guardrail must not be
conditional on retrieval succeeding.

**`temperature = 0.3`** made runs non-reproducible. Now 0.0. **No error
handling** on the provider call — a 429 became a bare 500. Now caught and
surfaced as `generation_error`. **No `max_tokens`**, so Groq reserved a huge
completion budget against the daily cap. Now 800.

---

## 4. Evaluation harness

**`RuntimeError: Event loop is closed`.** `ragas.evaluate()` calls
`asyncio.run()`, creating and closing a loop per call.
`ChatGoogleGenerativeAI` caches its `grpc.aio` client on first async use and
never invalidates it; the channel is bound to the loop that created it.
Fixed by dropping the cached client before each batch. `transport="rest"` is
not a workaround — the async path rewrites it back to `grpc_asyncio`.

**The judge budget never fit.** At `TOP_K=5`, ragas 0.3.9 costs ~13 calls per
row — `LLMContextPrecisionWithReference` alone is **one call per retrieved
context**. 61 rows × 13 ≈ 793 requests against a 500/day cap. Now ~9/row:
`ContextEntityRecall` off (it scored 0.000 — with a one-line reference its
entity set is near-empty, so it measured the reference's terseness) and
`AnswerRelevancy(strictness=1)`.

**Row timeout was 180s** against a metric that makes 5 sequential judge calls
at ~25s each. Now 600s, and a timeout skips the row instead of killing the run.

**Resume was broken three separate ways**, each silent:
- The run truncated the file it resumes from *before* writing its first row,
  so any interrupt discarded every completed row. Now backed up, and resume
  merges the live file with the backup rather than choosing between them.
- Resume keyed on row id alone. `build_eval_questions_v2.py` reassigns ids, so
  a stale outputs file served row 5's old answer as row 5's new answer — 39 of
  68 ids carried different questions at one point. Now compares question text.
- `_load_existing_scores` read `id` as int64 while ids are strings everywhere
  else, so the judge phase **rescored every row on every resume**. Visible in
  the logs as "Resuming judge phase: 1/40 already scored" followed by "40 rows
  pending", and never noticed.

`scripts/verify_patch.py` now checks unreachable statements, deleted or
duplicated definitions, and that the module imports — the classes of bug that
a syntax check passes.

---

## 5. Question set

`eval_questions_v1.csv` was written against a *file list*, not chunk content:
45 of 70 questions asked about filings absent from the index, and its ground
truth was unverifiable.

`eval_questions_v2.csv` is mined from chunks that are in the index. Each fact
row quotes the source line its figure came from, so ground truth is auditable.
68 questions: 50 RAGAS-scored, 18 behavioural. Audited before the run: **48 of
48 mined rows trace to a real line matched on company and fiscal year, 0
value mismatches, 0 degenerate year pairs, 0 missing companies.**

Two extraction rules do the work: labels match a canonical whitelist exactly
against the normalised non-numeric prefix (prefix matching harvested "Net loss
from disposal of subsidiaries" as `net loss`), and every column is parsed
including bare integers, so "column 1 = the filing's own fiscal year" is
computed against the real first column.

**Known ground-truth limitation: currency and scale are not asserted.** Filings
report in dollars, thousands or millions depending on a table header that is
often in a different chunk, and 20-F filers report in a local currency with a
USD convenience column. Row 21 (36Kr, a RMB filer) is a confirmed instance
where the mined value cannot be adjudicated against the answer. Treat mined
figures as positionally correct, not unit-qualified.

---

## 6. Results — 50 scored questions

Two independent judge passes over the identical 50 rows. Reported as
run A, with the error bar from run-to-run disagreement.

| metric | mean | error bar (MAD) |
|---|---|---|
| context_precision | 0.363 | ±0.004 |
| context_recall | 0.600 | ±0.010 |
| answer_relevancy | 0.599 | ±0.008 |
| faithfulness | 0.867 | ±0.043 |

**Split by outcome, the generator is not the bottleneck:**

| | precision | recall | relevancy | faithfulness | n |
|---|---|---|---|---|---|
| `ok` | 0.544 | 0.879 | 0.849 | **0.985** | 33 |
| `no_answer_in_context` | 0.000 | 0.000 | 0.000 | 0.714 | 14 |
| `unverified_source` | 0.100 | 0.500 | 0.977 | 0.417 | 2 |
| `entity_not_found` | 0.000 | 0.000 | 0.000 | 0.000 | 1 |

`context_recall` is effectively binary — 29 ones, 19 zeros, two halves. The
needed chunk is in the top-5 or it isn't; no partial credit, no gradual
degradation. **Given the right chunk, the system answers correctly and
faithfully (0.985).** Every aggregate weakness traces to retrieval.

**By category, ranked by recall:**

| category | precision | recall | faithfulness | n |
|---|---|---|---|---|
| fiscal_year_discrimination | **0.677** | **0.812** | 1.000 | 8 |
| exact_fact | 0.333 | 0.692 | 0.885 | 13 |
| disambiguation | 0.275 | 0.583 | 0.639 | 6 |
| fuzzy_no_ticker | 0.328 | 0.538 | 1.000 | 13 |
| typo_tolerance | 0.500 | 0.500 | 0.750 | 4 |
| language_parity | 0.125 | 0.500 | 1.000 | 2 |
| multi_year_comparison | **0.062** | **0.250** | 0.500 | 4 |

### Judge reliability

Two scoring passes over identical rows — same questions, answers, contexts and
references, different API key. Nothing about the system changed, so all
disagreement is judge noise.

| metric | A | B | shift | MAD | r | rows flipping side |
|---|---|---|---|---|---|---|
| context_precision | 0.363 | 0.367 | +0.004 | 0.004 | 0.997 | 0% |
| context_recall | 0.600 | 0.590 | −0.010 | 0.010 | 0.989 | 2% |
| answer_relevancy | 0.599 | 0.595 | −0.004 | 0.008 | 0.998 | 0% |
| faithfulness | 0.867 | 0.870 | +0.003 | 0.043 | 0.841 | 4% |

**The retrieval metrics are effectively deterministic at ±0.01.** A change
that moves `context_recall` by 0.05 is real signal, which is what makes the
next-steps list below measurable rather than speculative.

**`faithfulness` is four times noisier and unusable per-row.** Row 2 (BioCryst,
a demonstrably correct $38,252) scored **1.00 in one pass and 0.00 in the
other**. It is an NLI judgment over a handful of extracted statements, so one
statement flipping swings the row. Use the aggregate, never a single row, and
treat the `unverified_source` figure (n=2) as uninterpretable.

### The single most important result

**Row 26 (1st Source, total assets FY2022).** The system answered
**"$968,850 thousand"** with a source citation. The correct figure is
**$8,073,111 thousand** — wrong by a factor of 8. `context_recall = 0`: the
right chunk was never retrieved, and the model answered from a similar-looking
line rather than refusing.

So the honest-refusal story is only mostly true. 14 rows refused correctly when
retrieval missed, but **at least 1 of 50 produced a plausible, confidently
cited, wrong figure.** For a financial advisor product that is the headline
risk, and it should be reported ahead of any aggregate score. It is invisible
to `faithfulness`, which checks the answer against the retrieved context — and
the answer *was* consistent with what was retrieved. What was retrieved was
the wrong thing.

Two neighbouring rows are not errors: row 11 (aTyr) answered $34.0M correctly
by summing R&D and G&A rather than reading the total line, and row 35 (Acacia
Communications) answered $131,577 correctly. Both were marked down by metrics
rather than being wrong. Row 21 (36Kr) cannot be adjudicated — a RMB filer
with a USD convenience column, where the mined ground truth is unreliable.

### Behavioural rows (18, no judge calls)

| category | outcome | n |
|---|---|---|
| `subjective_gate` | 5/5 `subjective_no_verdict`, refused **without an LLM call** | 5 |
| `not_found_structural` | 4/4 declined (MSFT, TSLA, GOOGL, NVDA) | 4 |
| `not_found_fictional` | 3/3 declined | 3 |
| `off_topic` | 3/4 declined; 1 lost to provider quota | 4 |
| `edge_case_garbled` | 1 answered correctly, 1 declined | 2 |

**12 of 12 on the safety-critical categories, zero fabrication**, including
both Spanish investment-advice questions. The subjective gate short-circuits
before generation, which is why those rows survived an exhausted token budget.
`AAPL 2022 2021 2020 net sales???` returned all three years correctly; the
misspelled-name variant did not — the ticker path survives garbling, the fuzzy
name path does not.

## 7. What to do next, in order

Each item cites the measurement that motivates it.

**1. Add a lexical rank to retrieval.** *Evidence: precision 0.363, recall
0.600, and the precision distribution clusters at 0.20–0.25 — the useful chunk
is being retrieved at rank 4 or 5, under exhibit indexes and forward-looking
boilerplate.* Retrieval is pure dense cosine: grepping `rag/` and `backend/`
for BM25, `tsvector`, `ts_rank`, reranking or keyword search returns nothing
outside `.venv`. The questions are exact-fact lookups where the discriminating
signal is a literal match on a statement-line label, which a 384-dim embedding
of a 2,500-char chunk barely encodes. Fusing `ts_rank` against
`plainto_tsquery(question)` with the vector rank costs nothing inside the
`MATERIALIZED` CTE, where the candidate set is already a few hundred rows. No
reranker model, no extra API calls. **This is the highest-leverage change and
the eval can measure it directly: re-run the same 50 questions and compare.**

**2. Detect and refuse the confidently-wrong case.** *Evidence: row 26.* When
the top-ranked chunk's similarity is weak, the system answers anyway. The
`low_confidence` threshold (`max_score < 0.4`) is uncalibrated and, per this
run, not firing on the row that most needed it. The 50 scored rows are now the
first labelled data available to calibrate it — pick the threshold that
separates the recall-1 rows from the recall-0 rows.

**3. Re-chunk the unreadable documents, or drop them.** *Evidence: 5,924
chunks with `(cid:` markers, 1,544 chunks over 20k chars, largest 2.4 MB.*
Cheaper than any retrieval work and caps what any retriever can achieve.
`RAGAS/quarantine_bad_chunks.py` measures the blast radius and can remove them;
it reports which filings would disappear entirely first.

**4. Handle multi-row aggregation, or state that it is out of scope.**
*Evidence: multi_year_comparison at recall 0.250 / precision 0.062, the worst
category by a wide margin; and GPP FY2020, where the context held four
quarterly figures summing exactly to the ground-truth annual number and the
system refused.* Comparative table lines are poorly matched by embeddings of
"how did X change", and the system never combines rows it can see.

**5. Fix `match_rag_chunks.sql`** before the hosted deployment is used again —
identical ANN-before-filter defect.

**6. Tighten entity resolution.** *Evidence: `auris-medical` → `arris-group`
and `avid-bioservices` → `avid-technology`, both surfaced by
`typo_tolerance`; all three fictional companies resolve to
`amarin-corporation-plc` and answer correctly only because retrieval returns
nothing.* `_COMPANY_MATCH_THRESHOLD = 0.8` is uncalibrated, single-token
company names land exactly on it, and the ticker path matches the literal word
"Avid".

**7. Report the corpus's coverage limits.** FY2022 has 104 companies, FY2023
has one. Any demo question about a recent year will fail for reasons no
retrieval work will fix.

### On the numbers themselves

n = 50, spread over 7 categories, several with n = 2–4. Category means are
directional, not significant; only `exact_fact` (13) and `fuzzy_no_ticker`
(13) carry enough rows to stand alone. Report the aggregate and the
`ok` / `no_answer` split with confidence; treat the per-category ranking as a
prioritisation aid, which is what it is being used for here.
