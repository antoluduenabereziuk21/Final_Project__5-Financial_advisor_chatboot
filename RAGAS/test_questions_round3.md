# Test questions — round 3 (post-fix verification)

One thing this list depends on: I checked `bulk_load_results_supabase.csv` in full, not just the three companies from before. Every single loaded ticker starts with the letter **A** — 848 rows, zero exceptions (`AAPL`, `AMZN`, `AMD`, `ADBE`, `AMAT` are in; nothing past the A's is). That's consistent with the "~46% of the corpus loaded" figure from before: the load appears to have gone in alphabetical order and stopped partway. This matters directly for the "not in DB" tests below — a company starting with any other letter is a near-certain miss for a structural reason, not a retrieval-quality one, and that distinction is worth keeping straight when you read the results.

Where I could pull a specific fact from the actual parquet data, I did, so you have real ground truth to check the answer against rather than eyeballing plausibility. Where I couldn't (I don't have every company's parquet staged locally), I've marked it as a mechanism test rather than a ground-truth test — the point there is whether the *right document* got cited, not whether a specific number is correct.

## 1. Exact ticker mention (tests the ticker-recognition path in the entity resolver)

- **"How much did AAPL spend on stock buybacks in fiscal 2022?"**
  Ground truth: **$90.2 billion** repurchased in 2022 (Apple Inc., FY2022 10-K, Item 7).
- **"What was AAPL's quarterly dividend per share starting in May 2022?"**
  Ground truth: raised from **$0.22 to $0.23** per share, effective May 2022.
- **"What was AMAT's total backlog as of October 30, 2022?"**
  Ground truth: **$19,011 million**, of which ~32% not expected to be filled within 12 months; new export rules issued December 2022 were expected to reduce it by ~**$989 million**.

## 2. Fuzzy company name, no ticker (tests matching without exact-name typing)

- **"What percentage of Applied Optoelectronics' revenue in fiscal 2022 was denominated in RMB?"**
  Ground truth: **4.7%** (Item 7A, confirmed in the last round — this is the one that failed to surface even with correct filtering; worth re-running to see if it's still missed).
- **"What did American Airlines say about depreciating its aircraft?"** (no "Inc"/"Group" suffix, no ticker)
- **"Tell me about Antares Pharma's LEO Pharma agreement."**

## 3. Disambiguation (two companies sharing a first word — the exact case a false match earlier revealed as a risk)

- **"What was Applied Materials' backlog at the end of fiscal 2022?"** → should resolve to AMAT, not AAOI.
- **"What percentage of Applied Optoelectronics' revenue was in RMB in 2022?"** → should resolve to AAOI, not AMAT.
Run these back-to-back and confirm each cites the right company — this is the exact ambiguity a naive matcher would blur.

## 4. `company_name_mismatch = None` (unverified attribution — should surface the disclaimer honestly, not hide or over-trigger it)

These two chunks are ones I confirmed as `company_name_mismatch: null` directly from a live API response earlier, so retrieval finding them isn't hypothetical:

- **"What is the origin of Ascendis Pharma's goodwill, and has any impairment been recognized?"**
  Ground truth: goodwill from the 2007 acquisition of Complex Biosystems GmbH (now Ascendis Pharma GmbH); no impairments recognized in any period presented.
- **"What milestone payment did argenx receive when LEO Pharma exercised its option in September 2022?"**
  Ground truth: **€5.0 million**.
Expect the `unverified_source` disclaimer on both, since the answer's actual source chunk itself is unverified this time (not just noise riding along) — that's the "same-company uncertainty" case the flag is supposed to still catch after last round's fix.

## 5. Same company, different fiscal years (tests that `fiscal_year` extraction actually discriminates, not just company matching)

Both AAPL and AMAT have 2019–2022 loaded.

- **"What was Apple's revenue in fiscal 2019?"** vs **"What was Apple's revenue in fiscal 2022?"**
  Same company, different year — the two answers should cite different fiscal years and (most likely) different figures. If they come back suspiciously similar, the year filter probably isn't taking effect.

## 6. Company definitely not in the DB (tests fail-open behavior + honest "not found" reporting)

- **"What was Microsoft's revenue in fiscal 2022?"** — real company, real ticker (MSFT), guaranteed absent (wrong letter).
- **"What did Tesla report about battery supply risk?"** — same reasoning (TSLA).
- **"What is Zorvex Dynamics' main product line?"** — entirely fictional, a clean second control in case a real-but-absent company somehow partially matches something by coincidence.
Expect `entity_not_found` or an honest "no information available" — and specifically watch that it doesn't fuzzy-match one of the loaded A-companies by accident.

## 7. Typo / partial-name tolerance (stress-tests the 0.8 fuzzy threshold)

- **"What's going on with Antares Farma?"** (misspelled)
- **"How did Applied Materials Incorporated perform?"** (full legal name, spelled out, unlike the DB's slug)

## 8. Off-topic / low-relevance (tests `low_confidence`, not a company problem at all)

- **"What's a good recipe for lasagna?"**
- **"Explain how photosynthesis works."**
Expect a low-confidence or entity-not-found response, and specifically **no fabricated financial-sounding answer**.

## 9. Known unfixed gaps — worth confirming they still behave as documented, not fixing

- **Subjective/investment-advice gate (still keyword-based, easy to bypass):**
  "Should I invest in Apple?" (should trigger `subjective_no_verdict`) vs. a rephrase like "Is Apple a good long-term holding?" or "What would you recommend for my portfolio regarding Apple?" (tests whether rewording slips past the keyword list).
- **Multi-turn context (confirmed ignored — `conversation_history` is passed in but never used):**
  Ask "What was Apple's revenue in fiscal 2022?" then, as a follow-up in the *same* conversation, ask "What about in 2019?" without repeating "Apple." Prediction: the follow-up loses the company entirely (nothing in that second message resolves to anything) and either falls back to unfiltered full-corpus search or answers off-topic. This is the concrete, reproducible version of the conversation-memory gap from the report.

## 10. Language parity close-out

You raised early on whether English vs. Spanish wording was the real problem — testing showed filtering was the actual cause, not language, but that was never closed out with a matched EN/ES pair post-fix.

- **"¿Cuánto gastó Apple en recompra de acciones en el año fiscal 2022?"** — Spanish version of the AAPL buyback question above (ground truth: $90.2 billion). Same answer quality as the English version would be the expected, now-uninteresting result; a gap between them would be worth another look.
