# Financial Advisor Chatbot — Status Report

## What the app does

It's a retrieval-augmented (RAG) chatbot that answers questions about companies' 10-K/20-F annual filings, grounded in the actual filing text rather than the LLM's own knowledge. A user asks something like "What percentage of Applied Optoelectronics' revenue in FY2022 was denominated in RMB?" and the system finds the specific paragraph in that company's actual filing, hands it to an LLM as context, and returns an answer with a citation back to the source chunk (company, fiscal year, page range).

## Architecture

- **Frontend:** React + Vite, talks to the backend over `/api/chat`.
- **Backend:** FastAPI. Owns the chat endpoint, conversation bookkeeping, and orchestrates retrieval + generation.
- **Vector store:** Postgres + pgvector, either a local instance or a shared Supabase project (Supabase is what the running demo uses — currently holding ~185K of the ~404K chunks in the full corpus, about 46%).
- **Embeddings:** `all-MiniLM-L6-v2` (sentence-transformers), 384-dimensional, English-trained. Used to embed both the corpus at ingestion time and each incoming question at query time.
- **LLM:** Groq-hosted model, used to turn retrieved chunks into a natural-language answer. Falls back to a canned response if no LLM provider is configured, so the retrieval path is testable without an API key.

## Request flow

1. A question comes in to `/api/chat`.
2. An entity resolver checks the question text against the companies actually loaded in the corpus and, if it recognizes one confidently, extracts a company (and fiscal year, if mentioned) to scope the search. If nothing matches confidently, no filter is applied — the search stays open rather than risk scoping to the wrong thing.
3. The question is embedded and compared against the corpus (filtered, if step 2 found something) via cosine similarity in pgvector, returning the top-k most similar chunks.
4. A confidence flag is computed from what came back: no chunks → `entity_not_found`; weak similarity scores → `low_confidence`; a subjective/opinion-seeking question → `subjective_no_verdict`; the top chunk's source company was never cross-checked against the filing's actual registrant name → `unverified_source`; otherwise → `ok`.
5. The LLM generates an answer grounded in the retrieved chunks, with the flag steering how it's prompted (e.g. hedging language when the source is unverified). The flag is computed and enforced in code, not left to the LLM to decide or comply with.
6. The answer, its sources (with page numbers and relevance scores), and the flag are returned to the frontend.

## Bugs found and fixed this session

Verified against the actual codebase (not just the team's status doc, which had drifted from what the code does):

- **Fabricated citations on outage.** If the vector database wasn't reachable at startup, the backend used to still return a fake citation ("Apple Annual Report 2025") regardless of the question, instead of saying retrieval was unavailable. Fixed to report the outage plainly with zero sources.
- **Confidence flag conflated two different problems.** A source whose company attribution was never verified (~19.5% of the corpus) was being reported the same way as a weak retrieval match, even though "we're not sure this citation is real" and "we're not sure this is relevant" are different problems a user should be told about differently. Split into its own `unverified_source` flag with an explicit disclaimer.
- **That flag was scored over the wrong set of sources.** It checked every chunk retrieval returned, not just the one(s) the answer actually cited — so an unrelated, uncited chunk from a different company riding along in the results could falsely mark a fully correct, cleanly-sourced answer as unverified. Confirmed on a real query: a correct, well-cited Antares Pharma answer was getting flagged because two *unrelated* companies (Ascendis Pharma, argenx) happened to be retrieved alongside it and hadn't been verification-checked. Rescoped the check to the company actually being cited.
- **No retrieval filtering was ever applied.** The filter plumbing (by ticker/company/fiscal year) existed end-to-end in the retrieval layer but the live chat endpoint never populated it — every question, however specific, searched the full unfiltered corpus. This was the dominant cause of poor answers, more so than question language (see Test results below). Added an entity-resolution step that fuzzy-matches company mentions in the question against the corpus's actual company list and scopes retrieval accordingly, failing open (no filter) when it isn't confident. Deliberately filters on company name only, not ticker — ticker coverage in the loaded data is uneven (one company in the test set has 0% of its chunks with a ticker recorded), and combining an unset ticker filter with a company filter would silently return zero results for that company.
- **Python version incompatibility.** The backend used `datetime.UTC` (Python 3.11+ only) and bare `X | Y` type syntax that only works at runtime on 3.10+. On a 3.9 interpreter the app wouldn't start at all. Fixed and documented.

## Test results — conclusions

Testing used real chunks pulled directly from the loaded corpus (not made-up examples), with questions written against known, verifiable ground truth from the actual filing text.

- **Before the filtering fix:** only 1 of 3 highly specific, English-language test questions got the right answer. The other two retrieved real but wrong-fiscal-year content for the right company. Making the question more specific did not improve on the generic-question failure rate — this ruled out "the question needs to be worded better" and pointed at the missing filters as the real cause.
- **After the filtering fix:** 3 of 4 questions on a fresh batch answered correctly and were correctly cited, including a case that had failed twice before. The one remaining miss was qualitatively different from before: retrieval correctly scoped to the right company and fiscal year, but returned a different (also real, also relevant-looking) section of that filing instead of the one sentence with the specific figure asked about. The model correctly said it didn't have enough information rather than guessing — so this looks like a chunk-ranking limitation within an already-correctly-scoped document, not a fabrication risk.
- Also confirmed empirically: the language of the question (English vs. Spanish) had no measurable effect on retrieval quality. The corpus and embedding model are English, but that was not the bottleneck — the missing filters were.

## Known gaps / possible next steps

- **Conversation memory is not persisted.** History is held in an in-memory dictionary keyed by conversation ID and is lost on process restart; the `chat_messages` table in the schema exists for this but isn't being written to. Separately, the retrieval/generation code accepts a `conversation_history` parameter but never actually uses it — so even within a live process, a follow-up question is answered without knowledge of the prior turn.
- **Filtering is currently company + fiscal year only.** No filtering by section (e.g. restricting to "Risk Factors" or "MD&A"), form type, or accounting standard. This is the most direct lever for the remaining retrieval-ranking miss described above.
- **The subjective/investment-advice gate is keyword-based** and easy to bypass by rephrasing a question to avoid the trigger words.
- **Confidence thresholds are uncalibrated.** Both the low-confidence similarity-score cutoff and the new entity-match confidence threshold were chosen conservatively but not validated against a labeled question set. This is exactly what a RAGAS evaluation pass (mentioned as a later step at the start of this work) would give real numbers for.
- **Only ~46% of the full corpus is loaded** into the live Supabase database (185K of ~404K chunks). The rest exists locally but hasn't been bulk-loaded yet.
- **The API returns every retrieved source to the frontend**, not just the ones the model actually cited in its answer text — a minor precision gap in what gets shown as "sources" for a given response.
