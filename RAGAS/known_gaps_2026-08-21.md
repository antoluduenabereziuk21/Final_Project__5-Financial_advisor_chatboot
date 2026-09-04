# Known gaps — financial advisor chatbot

Consolidated from live testing after the 2026-08-21 fixes (no-fabrication fallback, scoped `unverified_source` flag, entity-resolved retrieval filtering). Ordered roughly by how much it affects answer quality/safety, not by how easy each is to fix. Each item states what was actually observed, not a guess.

## 1. `low_confidence` has no observable effect once an LLM is configured

`_compute_confidence_flag` correctly computes `low_confidence` when the top retrieval score is under 0.4. But `generate()` only branches on `entity_not_found`, `subjective_no_verdict`, and `unverified_source` — there's no `low_confidence` branch, and `_build_prompt` only adds a hedging instruction for `unverified_source`. So on the real LLM path, a `low_confidence` answer is generated identically to an `ok` one: no hedge, no disclaimer, nothing.

Observed directly: the "Antares Farma" query (see #4 below) had a top relevance score of 0.3558 — under the 0.4 cutoff, so `low_confidence` should have applied — and the response was a long, seven-section, confident-reading answer with zero indication the match was weak.

## 2. `confidence_flag` is never returned to the frontend

The `/api/chat` response body is `{answer, sources, conversation_id, message_id}` (see `ChatService.handle_message`'s return). The flag is computed and used internally but dropped before the response is built — there's no field in the API contract for it at all. Even if #1 were fixed and `low_confidence` got a hedge, there's currently no way for the frontend to show a confidence indicator, badge, or filter on it, because the value never leaves the backend.

## 3. Subjective/investment-advice gate is bypassed by English phrasing specifically

The keyword list in `_compute_confidence_flag` (`"mejor"`, `"recomendarías"`, `"debería"`, `"opinión"`, `"preferirías"`, `"cuál es la mejor"`) is Spanish-only. Three English test questions — *"Should I invest in Apple?"*, *"Is Apple a good long-term holding?"*, *"What would you recommend for my portfolio regarding Apple?"* — matched none of them, so `subjective_no_verdict` never fired. All three went through full retrieval + generation and produced long analyses that happened to end in a non-recommendation, but that came from the base prompt's soft instruction ("no des consejos de inversión"), not the code-enforced gate. The safety outcome held by LLM compliance, not by guarantee — this is a stronger claim than "the gate is keyword-based and reword-able," which was the prior framing.

## 4. Fuzzy entity-match threshold rejects the standard Spanish spelling of "Pharma"

`EntityResolver`'s per-token match takes the *weakest* token score. For "Antares Farma" (the correct Spanish spelling — no silent "h" — not really a typo for this app's actual users): `SequenceMatcher("farma", "pharma").ratio()` = **0.727**, below the 0.8 threshold. Result: no company filter applied at all, silent fail-open to a full unfiltered corpus search.

Concretely, that query returned 4 genuine Antares Pharma chunks plus one `assertio-holdings-inc` chunk (Assertio's own FY2022 10-K, correctly labeled, `company_name_mismatch: false` — not a data quality bug, just a different real company that discusses Antares/OTREXUP by name and scored close enough to enter the unfiltered top-5). The flag-scoping fix from earlier correctly excluded that chunk from the `unverified_source` check since it wasn't the top-scoring company — so the flag logic held up under this — but the underlying filter failure is real, and it's specifically triggered by Spanish spelling conventions on an app aimed at Spanish-speaking users.

## 5. LLM generated a fiscal year not present in the source

The Ascendis Pharma goodwill question retrieved a chunk whose own metadata says `fiscal_year: 2021`, `source_file: NASDAQ_ASND_2021.pdf` (confirmed from the raw API response). The generated Spanish answer stated *"ejercicio 2019"* and *"FY 2018-FY2019"* — neither year appears in the source text or its metadata. The correct year was in the prompt's source header (`_build_prompt` includes `FY{fiscal_year}` per source) and the model stated a different one anyway. This is a generation-time accuracy failure, distinct from every retrieval/citation problem fixed so far — grounding the *content* correctly doesn't guarantee the model won't misstate metadata that's right in front of it.

## 6. Retrieval ranking is inconsistent for borderline chunks, even within a correctly-scoped document

Three near-identical phrasings of the Applied Materials backlog question, against a company+year-filtered set of only 140 chunks:
- *"AMAT's total backlog as of October 30, 2022?"* → missed the $19,011M figure.
- *"AMAT total backlog as of October 30, 2022?"* (dropped the possessive) → got it correctly.
- *"Applied Materials' backlog at the end of fiscal 2022?"* → missed again.

Two of three failed on a small, correctly-filtered document with the answer sitting in one clearly-worded chunk. Filtering (item 2.6, already fixed) narrows the search space; it doesn't guarantee the right chunk wins the ranking within that space.

## 7. Applied Optoelectronics' RMB percentage (4.7%) has never been retrieved, in any phrasing tried

Confirmed present verbatim in `applied-optoelectronics-inc_2022_100` (Item 7A): *"During the year ended December 31, 2022, 4.7% of our revenue was denominated in RMB..."* Three different phrasings across two test rounds, post-filtering-fix, all retrieved a different, real, but wrong AAOI chunk (a revenue-by-geography table) instead. More consistently missed than the AMAT case above — this looks structural to that specific chunk/question pairing, not borderline. In every case the model correctly declined to fabricate the percentage rather than guessing, which is the no-fabrication fix working as intended, but the retrieval miss itself remains unresolved.

## 8. No multi-turn conversation support

`ConversationService` stores history in an in-memory `dict`, explicitly commented in the code as needing to be replaced with persisted storage — history is lost on process restart, and the `chat_messages` table that exists in the schema for this isn't being written to. Separately, and more immediately relevant to answer quality: `RootRAGAdapterImpl.generate_answer` accepts `conversation_history` as a parameter and never uses it anywhere in its body — it's not passed to retrieval or generation. A follow-up question that doesn't repeat the company by name (e.g. "What about in 2019?" after asking about Apple) has nothing for the entity resolver to match against and will fail open or answer off-topic.

## 9. Retrieval filtering covers company + fiscal year only

No filtering by section (`canonical_section`), form type, or accounting standard. This is the most direct lever against items #6 and #7 above — narrowing "AAOI FY2022" down further to "AAOI FY2022, Item 7A" would remove the wrong-section competitor chunks entirely rather than relying on embedding similarity to rank them correctly.

## 10. Confidence/match thresholds are uncalibrated guesses

Three separate numbers, none validated against a labeled question set: the 0.4 `low_confidence` score floor (demonstrated uninformative in the Antares Pharma/LEO Pharma test from the prior round, where a correct top match and unrelated noise scored within 0.015 of each other), the entity resolver's 0.8 per-token fuzzy-match floor (see #4), and the choice to use the top-scoring source's company as the scope for the `unverified_source` check rather than some other rule. This is exactly what a RAGAS evaluation pass — mentioned as a later step at the start of this project — would give real numbers for instead of judgment calls.

## 11. Only ~46% of the corpus is loaded, and specifically only companies A–something

Checked the full 848-row `bulk_load_results_supabase.csv`: every loaded ticker starts with "A". The load appears to have run alphabetically and stopped partway. Any question about a company starting with a later letter fails for a structural reason (never loaded), not a retrieval-quality reason — worth keeping distinct from the other items on this list when interpreting future test results.

## 12. API returns every retrieved source, not just the ones cited in the answer

`sources[]` in the response is the full top-k retrieval result, unfiltered by what the generated answer actually referenced in its text. A minor precision gap — the frontend (or a reviewer) can't currently tell which of the returned sources actually grounded the visible answer versus rode along unused.
