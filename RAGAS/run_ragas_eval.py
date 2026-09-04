"""
In-process RAGAS evaluation of the Financial Advisor Chatbot's full RAG
pipeline (entity resolution -> retrieval -> Groq generation), against
RAGAS/eval_questions_v1.csv.

"In-process" means this script imports and calls the same Python objects
FastAPI wires up at startup (backend/app/main.py's lifespan()) directly --
no HTTP server, no running backend needed. It talks straight to the local
Postgres/pgvector instance and to Groq.

Judge model is deliberately different from the generator model to avoid
LLM self-preference bias: the app generates answers with GROQ_MODEL
(openai/gpt-oss-120b by default, via Groq). RAGAS grades them with
RAGAS_JUDGE_MODEL (gemini-3.5-flash-lite by default, via Google's Gemini
API -- see JUDGE_MODEL below for the full story of why this ended up on
a completely different provider, not just a different model: Groq's TPD
wall, then Cerebras' $0-balance dead end, before landing here).

Run with the Windows venv that already has this repo's dependencies
(rag/.venv), from the project root:

    rag\\.venv\\Scripts\\python.exe -m pip install -r RAGAS\\requirements_eval.txt
    rag\\.venv\\Scripts\\python.exe RAGAS\\run_ragas_eval.py

Outputs:
    RAGAS/results/raw_pipeline_outputs.csv   -- every row: what the
        pipeline actually retrieved/answered/flagged, regardless of
        whether it's RAGAS-scored.
    RAGAS/results/ragas_scores.csv           -- per-row RAGAS metric
        scores, for the subset of rows that have a real, corpus-grounded
        ground_truth_answer (see SKIP_RAGAS_CATEGORIES below).
    RAGAS/results/summary.md                 -- aggregate scores +
        the behavioral-only rows' confidence_flag, for eyeballing.

Why not every row gets a RAGAS score: rows in categories like
off_topic, not_found_fictional, not_found_structural, subjective_gate,
and subjective_gate_bypass are testing REFUSAL/flag behavior, not factual
grounding -- "ground_truth_answer" for those is a description of expected
behavior, not a fact the retrieved context should support. Forcing those
through faithfulness/context-precision would produce meaningless near-zero
scores that look like pipeline failures but aren't. They're still run
through the pipeline and logged (answer + confidence_flag) in
raw_pipeline_outputs.csv and summary.md so you can eyeball whether the
refusal/flag behavior itself is correct -- just not RAGAS-scored.
"""

from __future__ import annotations

import asyncio
import csv
import shutil
import sys  # noqa: F811

import os  # noqa: E402  (needed here: the offline flags must be set pre-import)

# all-MiniLM-L6-v2 is cached locally, but sentence-transformers still HEADs
# huggingface.co on every model load to check for updates -- and blocks on
# 5 retries when the network is unreachable, twice per run (once for
# retrieval's embed_text, once for RAGAS's answer_relevancy embeddings).
# An eval that depends on a remote host for a local model is a flake
# generator. Set RAGAS_HF_ONLINE=1 to allow the network back, e.g. the first
# time you run on a machine where the model is not cached yet.
if os.getenv("RAGAS_HF_ONLINE") != "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# retrieved_contexts_joined can exceed Python's default 131,072-byte csv
# field limit: one chunk in the corpus is 112,893 chars of failed PDF text
# extraction, and joined with its four neighbours the field hits ~140,493.
# Without this, _load_existing_outputs() cannot read back a file this script
# wrote. Halve down from sys.maxsize because field_size_limit takes a C long,
# which is 32-bit on Windows and overflows.
_csv_limit = sys.maxsize
while True:
    try:
        csv.field_size_limit(_csv_limit)
        break
    except OverflowError:
        _csv_limit //= 2
import os
import sys
import time
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
for p in (str(_PROJECT_ROOT), str(_BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_PROJECT_ROOT / ".env")

# Defaults to v2 (mined from the live index, ground truth carries its source
# line) and falls back to v1 only if v2 has not been generated yet.
# RAGAS_EVAL_CSV overrides both.
_V2 = _PROJECT_ROOT / "RAGAS" / "eval_questions_v2.csv"
EVAL_CSV = (
    Path(os.environ["RAGAS_EVAL_CSV"]) if os.getenv("RAGAS_EVAL_CSV")
    else (_V2 if _V2.exists() else _PROJECT_ROOT / "RAGAS" / "eval_questions_v1.csv")
)
RESULTS_DIR = _PROJECT_ROOT / "RAGAS" / "results"
TOP_K = 5

# Rows per RAGAS judge batch -- i.e. how much work is checkpointed at
# once. Added 2026-09-02 alongside per-batch checkpointing: Gemini free
# tier's confirmed 500 requests/day cap means a single evaluate() call
# over all 61 eligible rows (305+ actual jobs) routinely gets cut off
# mid-run, and evaluate() with raise_exceptions=True (used per-batch,
# see main()) returns NOTHING for a batch if even one job in it fails --
# not just the failed job, the whole batch's otherwise-successful
# results too. Dropped from 5 to 1 the same day after that cost a real
# batch: a single job timeout (TimeoutError, not quota) on job 24/25 of
# a 5-row batch discarded ~50-55 already-spent API calls across 4
# fully-succeeded rows, saving 0 of them. At 1, the same class of
# failure loses at most one row's ~8-11 calls. The cost is more
# executor setup/teardown overhead per row -- worth it against a tight,
# non-renewable daily call budget.
BATCH_ROWS = 1

# Categories whose ground_truth_answer describes expected BEHAVIOR (refuse,
# flag, decline) rather than a fact the retrieved context should support.
# These are still run through the pipeline and logged, just not scored by
# RAGAS's context/faithfulness/relevancy metrics.
# RAGAS_RUN_TAG names an independent judge run. The judge is an LLM: even at
# temperature 0 it is not deterministic across calls, so a single scoring pass
# gives point estimates with no error bars, and you cannot tell a real
# difference from judge noise. Setting RAGAS_RUN_TAG=run2 writes to
# ragas_scores_run2.csv / summary_run2.md instead, so the resume logic does
# NOT skip the already-scored rows and the same 50 questions get judged again
# independently. compare_judge_runs.py then reports test-retest agreement.
_RUN_TAG = os.getenv("RAGAS_RUN_TAG", "").strip()
_TAG_SUFFIX = f"_{_RUN_TAG}" if _RUN_TAG else ""


def _scores_path():
    return RESULTS_DIR / f"ragas_scores{_TAG_SUFFIX}.csv"


def _summary_path():
    return RESULTS_DIR / f"summary{_TAG_SUFFIX}.md"


SKIP_RAGAS_CATEGORIES = {
    # edge_case_garbled tests whether a garbled question still RESOLVES to the
    # right company -- that is observable from resolved_company_filter and
    # confidence_flag, with no judge involved. Its ground truth is behavioural
    # prose ("should resolve to Apple Inc FY2022 revenue"), not a figure with
    # a source line, so scoring it against retrieved context measures nothing
    # and costs 18 judge requests.
    "edge_case_garbled",
    "off_topic",
    "not_found_fictional",
    "not_found_structural",
    "subjective_gate",
    "subjective_gate_bypass",
}

# Full history (2026-09-01), in order:
# 1. llama-3.3-70b-versatile: not accessible on this plan tier ("Contact
#    Sales" on the pricing page -- gated, not a wrong name).
# 2. qwen/qwen3.8-27b, qwen/qwen3.6-27b, openai/gpt-oss-20b: all three
#    403 model_permission_blocked_project under the original
#    GROQ_API_KEY's "cosop" project.
# 3. A separate Groq project/key (RAGAS_JUDGE_GROQ_API_KEY) whose
#    allowlist explicitly permitted qwen/qwen3.8-27b -- worked for
#    exactly one model call before repeatedly hitting that SEPARATE
#    project's own 200,000 TPD ceiling mid-run, confirmed directly from
#    Groq's 429 body (Used ~199,600-199,800/200,000) across THREE
#    separate full/partial runs, on two different Groq orgs. Groq's
#    on_demand free-tier default, not a config bug -- no RunConfig
#    tuning fixed it, because the constraint is a total daily token
#    budget, not a pacing problem.
# 4. Moved off Groq entirely to Cerebras (gemma-4-31b, 1,000,000 TPD
#    per Cerebras' own docs). Dead end for a different reason: the
#    account's actual balance was $0.00 with no active subscription --
#    every call 402 payment_required_error. Cerebras' advertised
#    zero-cost free tier did not materialize for this account in
#    practice (a real gap, not a config issue -- confirmed via the
#    account's own Billing > Overview page on 2026-09-01).
# 5. Actual fix: Google Gemini (GEMINI_API_KEY, see
#    _build_judge_and_embeddings below). Confirmed via Google's own
#    pricing docs on 2026-09-01: Flash-family models are "free of
#    charge" for input/output tokens on the free tier -- no daily
#    token-budget wall at all (the exact failure mode that killed every
#    Groq attempt), and no credit-balance gate (the failure mode that
#    killed Cerebras). The binding constraint instead is requests/day,
#    which Google does not publish a fixed number for -- it's
#    account/tier-specific, visible only at
#    aistudio.google.com/rate-limit. Real trade-off, not free of one:
#    Google's free-tier terms state "content used to improve our
#    products" -- real financial-document Q&A content sent to the judge
#    is usable by Google, not just processed and discarded. gemini-2.5-
#    flash-lite chosen as judge model: cheapest/highest-throughput Flash
#    variant, likely to have the most free-tier request headroom of the
#    family, and (like Cerebras) a genuinely different vendor/lineage
#    from the openai/gpt-oss-120b generator.
JUDGE_MODEL = os.getenv("RAGAS_JUDGE_MODEL", "gemini-3.5-flash-lite")
GENERATOR_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _load_questions() -> list[dict]:
    with open(EVAL_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows read from {EVAL_CSV}")
    return rows


async def _build_pipeline():
    """Wires up the same objects backend/app/main.py's lifespan() builds,
    minus the FastAPI app itself. Returns (adapter, entity_resolver,
    db_client) so the caller can close db_client when done."""
    from rag.llm.generator import configure as configure_llm
    from rag.vector_store.client import VectorDbClient
    from rag.vector_store.repository import VectorRepository
    from app.rag.adapter import RootRAGAdapterImpl
    from rag.retrieval.entity_resolver import EntityResolver, KnownEntity

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set (checked .env at project root). "
            "Generation and RAGAS judging both need it."
        )
    configure_llm("groq")

    db_client = VectorDbClient(
        host=os.getenv("VECTOR_DB_HOST", "localhost"),
        port=int(os.getenv("VECTOR_DB_PORT", "5432")),
        user=os.getenv("VECTOR_DB_USER", "ml_engineer"),
        password=os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026"),
        database=os.getenv("VECTOR_DB_NAME", "financial_rag_vectors"),
    )
    await db_client.connect()
    repo = VectorRepository(db_client)

    known_rows = await repo.list_companies()
    known_entities = [
        KnownEntity(company=row["company"], ticker=row.get("ticker"))
        for row in known_rows
        if row.get("company")
    ]
    entity_resolver = EntityResolver(known_entities)
    print(f"Entity resolver ready with {len(known_entities)} known companies.")

    adapter = RootRAGAdapterImpl(repo=repo)
    return adapter, entity_resolver, db_client


def _row_is_usable(row: dict) -> bool:
    """A row counts as completed work only if it holds a real answer. A
    provider 429 or a pipeline exception is transient -- reusing it would
    bake the failure in permanently."""
    return bool(row.get("answer")) and row.get("confidence_flag") not in (
        "pipeline_error", "generation_error")


def _read_output_rows(path) -> list[dict]:
    if not path.exists() or path.stat().st_size < 200:
        return []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as exc:  # a half-written file is not a reason to die
        print(f"  (could not read {path.name}: {exc})")
        return []


def _load_existing_outputs(raw_path) -> dict[str, dict]:
    """Completed rows from a previous run, so a rerun never re-spends quota
    on work already paid for.

    Reads BOTH the live file and its .prev backup and takes the union,
    keyed by row id, with the live file winning ties. That matters because
    _run_pipeline truncates the live file before writing its first row: an
    interrupt leaves the completed rows only in .prev and the partial rows
    only in the live file. Preferring one over the other loses whichever
    half you did not pick; merging loses nothing.
    """
    existing: dict[str, dict] = {}
    for path in (raw_path.with_suffix(".csv.prev"), raw_path):
        for row in _read_output_rows(path):
            if _row_is_usable(row):
                existing[row["id"]] = row

    seen = {r["id"] for pth in (raw_path.with_suffix(".csv.prev"), raw_path)
            for r in _read_output_rows(pth)}
    failed = len(seen) - len(existing)
    if failed > 0:
        print(f"{failed} previously-failed row(s) will be regenerated.")
    if existing:
        print(f"{len(existing)} completed row(s) recovered and will be reused.")
    return existing
async def _run_pipeline(adapter, entity_resolver, rows: list[dict]) -> list[dict]:
    """Runs every eval question through the real pipeline (entity
    resolution -> retrieve -> generate), sequentially -- Groq free-tier
    rate limits make concurrent generation calls unreliable, and we want
    a clean per-row log to debug against if something breaks partway.
    Writes raw_pipeline_outputs.csv incrementally so a crash mid-run
    doesn't lose completed rows. Resumes from a previous run's output
    file when one exists: rows that already generated successfully are
    reused as-is (no repeat API call); only rows missing or previously
    errored are (re)run."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS_DIR / "raw_pipeline_outputs.csv"
    existing = _load_existing_outputs(raw_path)
    if existing:
        print(f"Resuming: {len(existing)}/{len(rows)} rows already completed "
              f"in a previous run, will be reused as-is.")

    fieldnames = [
        "id", "category", "question", "expected_company", "expected_ticker",
        "expected_fiscal_year", "ground_truth_answer",
        "resolved_company_filter", "resolved_fiscal_year_filter",
        "num_sources_retrieved", "confidence_flag", "answer",
        "retrieved_contexts_joined",
    ]

    # Back up before truncating. open(raw_path, "w") destroys the file this
    # run resumes FROM, before a single row has been written -- so any
    # interrupt after this point throws away every completed row.
    if raw_path.exists() and raw_path.stat().st_size > 0:
        shutil.copy2(raw_path, raw_path.with_suffix(".csv.prev"))

    outputs = []
    with open(raw_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, row in enumerate(rows, 1):
            question = row["question"]
            row_id = row["id"]

            # Resume keys on id AND question text: build_eval_questions_v2.py
            # reassigns ids from scratch, so a stale outputs file would serve
            # row 5's old answer as row 5's new answer.
            if row_id in existing and existing[row_id].get("question") == question:
                print(f"[{i}/{len(rows)}] ({row['category']}) SKIP (already completed) {question[:60]}")
                out_row = existing[row_id]
                contexts = (
                    out_row["retrieved_contexts_joined"].split("\n---CHUNK---\n")
                    if out_row.get("retrieved_contexts_joined")
                    else []
                )
                writer.writerow(out_row)
                f.flush()
                outputs.append({**out_row, "_contexts_list": contexts})
                continue

            # RAGAS_SCORED_ONLY=1 generates only the rows RAGAS will score.
            # Behavioural rows run unfiltered, so their context can reach the
            # 20,000-char cap on all five chunks (~24.5k tokens/call) versus
            # ~3.5k for a company-filtered question.
            if os.getenv("RAGAS_SCORED_ONLY") == "1" and row["category"] in SKIP_RAGAS_CATEGORIES:
                print(f"[{i}/{len(rows)}] ({row['category']}) SKIP (RAGAS_SCORED_ONLY)")
                continue

            print(f"[{i}/{len(rows)}] ({row['category']}) {question[:80]}")

            resolved = entity_resolver.resolve(question)
            filters = resolved.as_filters_dict() or None

            try:
                result = await adapter.generate_answer(
                    question=question,
                    conversation_history=[],
                    filters=filters,
                    top_k=TOP_K,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"    !! pipeline error: {exc}")
                result = {
                    "answer": f"[PIPELINE ERROR: {exc}]",
                    "confidence_flag": "pipeline_error",
                    "sources": [],
                }

            sources = result.get("sources", [])
            contexts = [s.get("content") or s.get("text_snippet", "") for s in sources]

            out_row = {
                "id": row["id"],
                "category": row["category"],
                "question": question,
                "expected_company": row.get("company", ""),
                "expected_ticker": row.get("ticker", ""),
                "expected_fiscal_year": row.get("fiscal_year", ""),
                "ground_truth_answer": row.get("ground_truth_answer", ""),
                "resolved_company_filter": ";".join(filters.get("company", []))
                if filters and filters.get("company") else "",
                "resolved_fiscal_year_filter": filters.get("fiscal_year", "")
                if filters else "",
                "num_sources_retrieved": len(sources),
                "confidence_flag": result.get("confidence_flag", ""),
                "answer": result.get("answer", ""),
                "retrieved_contexts_joined": "\n---CHUNK---\n".join(contexts),
            }
            writer.writerow(out_row)
            f.flush()

            outputs.append({**out_row, "_contexts_list": contexts})

            # Be gentle with Groq's free-tier rate limits: one generation
            # call per row already happened above; leave a little room
            # before the next one.
            await asyncio.sleep(1.0)

    print(f"\nWrote {len(outputs)} rows to {raw_path}")
    return outputs

def _get_sample_and_dataset_classes():
    """SingleTurnSample/EvaluationDataset moved around across ragas 0.2.x
    releases (ragas.dataset_schema vs top-level re-export). Try both so
    this doesn't break on whichever version ends up installed."""
    try:
        from ragas import SingleTurnSample, EvaluationDataset
    except ImportError:
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    return SingleTurnSample, EvaluationDataset


def _load_existing_scores(scores_path) -> dict[str, dict]:
    """Loads a previous ragas_scores.csv (if any) so a rerun only
    (re-)judges rows that are missing or incompletely scored. Added
    2026-09-02 after discovering Gemini's free tier enforces a hard,
    confirmed-live 500 requests/day cap per project/model
    (quota_id=GenerateRequestsPerDayPerProjectPerModel-FreeTier) --
    the RAGAS scoring phase had no checkpointing at all before this,
    so a quota cutoff mid-run (it hit at job ~170/305, roughly 55%
    through) discarded that entire day's judge calls on the next
    rerun. A row counts as complete only if every metric column is
    non-null -- a row with even one NaN metric is retried, since a
    partial failure there most likely means the quota wall cut it off
    mid-row rather than that metric genuinely being unscoreable."""
    if not scores_path.exists():
        return {}
    # An empty or headerless file is not a resume point. _write_summary
    # writes scores_df even when the judge phase scored nothing (e.g. a
    # RAGAS_MAX_ROWS=0 diagnostic run), leaving a 2-byte file that
    # pd.read_csv rejects with EmptyDataError and that killed the run
    # AFTER the whole pipeline phase had already completed.
    try:
        # dtype={"id": str} is load-bearing. Row ids are strings everywhere
        # else in this script; pandas infers the id column as int64, so
        # `row_id not in existing_scores` was ALWAYS true and the judge phase
        # rescored every row on every resume. Silent, and expensive: it turned
        # a 21-row resume into a 50-row rerun, 189 wasted requests against a
        # 500/day cap. Visible in the 2026-09-02 log as "Resuming judge phase:
        # 1/40 rows already fully scored" followed by "40 rows pending".
        df = pd.read_csv(scores_path, dtype={"id": str})
    except (pd.errors.EmptyDataError, ValueError):
        return {}
    if df.empty or "id" not in df.columns:
        return {}
    metric_cols = [c for c in df.columns if c not in (
        "id", "user_input", "response", "retrieved_contexts", "reference"
    )]
    if not metric_cols:
        return {}
    complete = df[df[metric_cols].notna().all(axis=1)]
    return {str(row["id"]): row.to_dict() for _, row in complete.iterrows()}


def _build_ragas_dataset(outputs: list[dict]):
    """RAGAS_ONLY_CONFIDENCE_OK=1 (added 2026-09-02, alongside the 45-row
    budget squeeze): restricts scoring to rows the pipeline itself marked
    confidence_flag=='ok' -- i.e. rows with no retrieval/confidence
    caveat already attached, the closest thing to a 'solid generation'
    filter available from data already on disk. This does NOT change
    which rows are eligible for scoring on quality grounds, only which
    ones get spent against a tight per-key call budget -- unverified_source
    and low_confidence rows are just as real and should be scored too
    once quota isn't the binding constraint."""
    SingleTurnSample, EvaluationDataset = _get_sample_and_dataset_classes()
    only_ok = os.getenv("RAGAS_ONLY_CONFIDENCE_OK") == "1"
    skip_unresolved = os.getenv("RAGAS_SKIP_UNRESOLVED") == "1"

    samples = []
    scored_ids = []
    for out in outputs:
        if out["category"] in SKIP_RAGAS_CATEGORIES:
            continue
        if not out["ground_truth_answer"]:
            continue
        if only_ok and out.get("confidence_flag") != "ok":
            continue
        # RAGAS_SKIP_UNRESOLVED=1: drop rows where the entity resolver
        # produced no company filter. Verified 2026-09-02: resolution
        # succeeds iff the ticker exists in the ACTIVE index, with zero
        # exceptions across all 62 ticketed rows (17 resolved / 17 in
        # index, 45 unresolved / 45 absent). Those 45 rows retrieve five
        # chunks from an unrelated company and the generator correctly
        # refuses, so faithfulness/precision on them scores a refusal
        # against irrelevant context -- uninterpretable, and ~9 judge
        # calls each of a 500/day budget.
        if skip_unresolved and not str(out.get("resolved_company_filter") or "").strip():
            continue
        # A row whose generation failed has no answer to score -- its
        # "answer" is the provider-error string. Scoring it burns ~9 judge
        # requests to measure a 429.
        if out.get("confidence_flag") == "generation_error":
            continue
        samples.append(
            SingleTurnSample(
                user_input=out["question"],
                response=out["answer"],
                retrieved_contexts=out["_contexts_list"] or [""],
                reference=out["ground_truth_answer"],
            )
        )
        scored_ids.append(out["id"])

    return EvaluationDataset(samples=samples), scored_ids


class _SingleSampleChat:
    """Mixin that forces every call's `n` to 1 right before it reaches the
    API, regardless of what ragas/langchain requested upstream.

    Originally added for Groq (its API hard-rejects any `n` other than 1:
    'n : number must be at most 1', independent of model/tier). Also
    applied when the judge briefly ran on Cerebras, on the same
    defensive logic. NOT applied to the current Gemini judge -- see
    _build_judge_and_embeddings()'s docstring for why. Left defined here
    in case a future judge swap lands back on a Groq-like provider.
    Binding `n=1` via LangChain's `.bind()` is not reliable here because
    call-time kwargs from ragas can override bound ones; overriding
    _generate/_agenerate and clobbering kwargs["n"] immediately before the
    underlying request is built is the one point guaranteed to run last.
    Trade-off worth knowing: this silently drops whatever self-consistency
    sampling a metric wanted and always scores off a single completion --
    a real reduction in that metric's statistical stability, not a
    cosmetic shim."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        kwargs["n"] = 1
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        kwargs["n"] = 1
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _build_judge_and_embeddings():
    """Judge: gemini-3.5-flash-lite via Google's Gemini API (see
    JUDGE_MODEL's comment above for the full history of why the judge
    ended up here, off both Groq and Cerebras). Needs GEMINI_API_KEY
    (create one free at aistudio.google.com/apikey -- no card required
    to get the key itself, unlike Cerebras).
    n=1 handled via LangchainLLMWrapper(bypass_n=True), NOT the
    _SingleSampleChat mixin: read ragas/llms/base.py directly (installed
    in this venv) on 2026-09-01 after the mixin failed to stop 400s from
    Gemini ('Multiple candidates is not enabled for this model'). Root
    cause: ragas's wrapper does `self.langchain_llm.n = n` -- it mutates
    the chat model's own `n` field in place before each call -- it does
    NOT pass n as a call-time kwarg the way Groq's client does. The
    mixin clobbers kwargs["n"], which this code path never reads, so it
    silently did nothing. `bypass_n=True` is ragas's own documented
    escape hatch (see LangchainLLMWrapper.__init__): it skips that
    mutation entirely, so the model keeps its own default n=1 on every
    call. Confirmed via ragas source, not guessed.
    Embeddings: the same all-MiniLM-L6-v2 model already used everywhere
    else in this pipeline, so answer_relevancy's embedding space matches
    what retrieval itself uses -- and so this needs no OpenAI key."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    judge_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=JUDGE_MODEL,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.0,
        ),
        bypass_n=True,
    )
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    return judge_llm, embeddings


def _run_ragas(dataset, judge_llm, embeddings, raise_exceptions=False):
    from ragas import evaluate
    try:
        from ragas.run_config import RunConfig
    except ImportError:
        from ragas import RunConfig
    # Legacy (pre-0.4) metrics API -- deliberately not ragas.metrics.collections,
    # whose scorer objects use a different (fully-async, evaluate()-independent)
    # orchestration model. These are what evaluate(dataset=..., metrics=...)
    # below expects. NOTE: the response-relevancy metric's legacy class name
    # is `AnswerRelevancy`, not `ResponseRelevancy` -- confirmed against
    # ragas's docs on 2026-08-31; double-check against whatever ragas version
    # actually installs if this import fails.
    from ragas.metrics import (
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ContextEntityRecall,
        AnswerRelevancy,
        Faithfulness,
    )

    # NoiseSensitivity deliberately dropped: on 2026-09-01 it was the metric
    # that crashed a full run (asyncio.TimeoutError at job 9/366, ~85-90s/it
    # even on successful jobs -- it runs multiple sequential statement-level
    # judge calls per row internally, unlike the other 5 metrics). With
    # raise_exceptions=True that single failure discarded the whole run's
    # progress; with raise_exceptions=False (restored below) it would just
    # keep silently contributing NaNs the way it did in the very first full
    # run (n=1 non-null out of 61 rows -- already useless as a metric).
    # Losing 1 of 6 metrics is a better trade than repeatedly risking or
    # wasting an entire ~366-job run on it.
    # Judge-call budget per row (ragas 0.3.9, TOP_K=5 contexts):
    #   LLMContextPrecisionWithReference : 1 call PER CONTEXT  -> 5
    #   LLMContextRecall                 : 1
    #   ContextEntityRecall              : 2
    #   AnswerRelevancy                  : `strictness` calls  -> 3 by default
    #   Faithfulness                     : 2
    # = ~13 calls/row. 52 rows = ~676 requests, against a 500/day free-tier
    # cap -- the run cannot fit in one day at defaults, retries excluded.
    # ContextEntityRecall is off by default: `reference` here is a one-line
    # factoid ("$90.2 billion repurchased in FY2022"), so its entity set is
    # near-empty and it scored 0.000 on the only row ever completed. It is
    # measuring the reference's terseness, not retrieval. Set
    # RAGAS_ENTITY_RECALL=1 to restore it.
    # AnswerRelevancy strictness drops 3 -> 1: more per-row variance, same
    # expectation over the run mean. RAGAS_RELEVANCY_STRICTNESS overrides.
    # Defaults => 5+1+1+2 = 9 calls/row.
    strictness = int(os.getenv("RAGAS_RELEVANCY_STRICTNESS", "1"))
    metrics = [
        LLMContextPrecisionWithReference(),
        LLMContextRecall(),
        AnswerRelevancy(strictness=strictness),
        Faithfulness(),
    ]
    if os.getenv("RAGAS_ENTITY_RECALL") == "1":
        metrics.insert(2, ContextEntityRecall())

    # Judge moved to Gemini (see JUDGE_MODEL's comment for the full
    # story) after Groq's TPD wall and Cerebras' $0-balance dead end.
    # Confirmed live on 2026-09-02: Gemini's free tier enforces a hard
    # 500 requests/day cap for this model
    # (GenerateRequestsPerDayPerProjectPerModel-FreeTier) -- not an RPM
    # pacing limit, a daily budget, same category of problem as Groq's
    # TPD wall. max_workers=1 stays conservative since RPM headroom is
    # still unpublished/account-specific; the real fix for the daily
    # cap is the batch-checkpointing in main(), not a worker count.
    # max_retries/max_wait trimmed from 6/90 to 3/30: once the daily
    # quota is actually exhausted, retries can't succeed until it
    # resets, so a long backoff just burns wall-clock for nothing --
    # confirmed by the 2026-09-02 run, which spent ~4h20m mostly
    # retrying against an already-dead quota before main()'s batch
    # loop below existed to detect and stop that early.
    # raise_exceptions is now caller-controlled (see main()): batches
    # pass True so a quota error surfaces immediately and distinctly
    # from a benign NaN, instead of being silently absorbed -- the
    # earlier all-False design made a dead quota indistinguishable
    # from a handful of ordinary failures without downloading the CSV
    # and counting NaNs by hand. Losing one batch's progress on a
    # raised exception is an accepted, now-small cost (batches are a
    # few rows each, not the whole run).
    # timeout 180 -> 600. 180s was set when the metric list was different.
    # LLMContextPrecisionWithReference alone issues one judge call PER
    # RETRIEVED CONTEXT -- 5 sequential calls at TOP_K=5 -- and at ~25s per
    # call on this judge, plus a tenacity retry, a single row exceeds 180s
    # routinely. Confirmed on 2026-09-03: batch 22/50 died at 3m05s with 0 of
    # 4 metrics complete. Env-overridable.
    _timeout = int(os.getenv("RAGAS_ROW_TIMEOUT", "600"))
    run_config = RunConfig(max_workers=1, timeout=_timeout, max_retries=3, max_wait=30)

    # ---- FIX (2026-09-02): "RuntimeError: Event loop is closed" on batch 2+
    # ragas.evaluate() calls asyncio.run(), which creates AND CLOSES a fresh
    # event loop on every call. ChatGoogleGenerativeAI caches its async gRPC
    # client on `.async_client_running` the first time it is used inside a
    # running loop (see langchain_google_genai/chat_models.py, the
    # `async_client` property) and never invalidates it. The grpc.aio channel
    # inside it is bound to the loop it was created on, so batch 2 tries
    # loop.create_task() on batch 1's closed loop -> RuntimeError.
    # transport="rest" is NOT a workaround: that same property force-rewrites
    # "rest" to "grpc_asyncio" for the async path. Dropping the cached client
    # before each batch makes the next evaluate() build a channel on its own
    # loop. Costs nothing; the dead channel was unusable anyway.
    inner = getattr(judge_llm, "langchain_llm", None)
    if inner is not None and hasattr(inner, "async_client_running"):
        inner.async_client_running = None

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=embeddings,
        run_config=run_config,
        raise_exceptions=raise_exceptions,
    )
    return result


def _write_summary(outputs: list[dict], scores_df, scored_ids: list[str]) -> None:
    """scores_df now arrives pre-merged from main()'s batch-checkpoint
    loop (already has an 'id' column and every metric column, one row
    per fully- or partially-scored id) -- this function no longer talks
    to ragas_result directly, since main() may be calling it after a
    quota cutoff stopped the judge phase partway through, not just
    after a full clean run."""
    summary_path = _summary_path()
    # Don't leave a zero-column file behind when nothing was scored -- it is
    # not a checkpoint, and the next run has to be able to read it.
    if not scores_df.empty:
        scores_df.to_csv(_scores_path(), index=False)

    metric_cols = [c for c in scores_df.columns if c not in (
        "id", "user_input", "response", "retrieved_contexts", "reference"
    )]
    means = scores_df[metric_cols].mean(numeric_only=True) if metric_cols else pd.Series(dtype=float)

    lines = [
        "# RAGAS Evaluation Summary",
        "",
        f"Generator model: `{GENERATOR_MODEL}` (Groq)  ",
        f"Judge model: `{JUDGE_MODEL}` (Gemini)  ",
        f"Total questions run through pipeline: {len(outputs)}  ",
        f"Questions RAGAS-scored so far (excludes behavioral-only categories): {len(scored_ids)}",
        "",
        "## Aggregate scores (mean across scored rows -- may be a partial",
        "## run if the judge phase stopped early on a quota cutoff; check",
        "## the terminal output above for whether this run completed)",
        "",
        "| Metric | Mean |",
        "|---|---|",
    ]
    for metric, val in means.items():
        lines.append(f"| {metric} | {val:.3f} |")

    lines += [
        "",
        "## Behavioral-only rows (not RAGAS-scored -- eyeball confidence_flag)",
        "",
        "| id | category | confidence_flag | answer (truncated) |",
        "|---|---|---|---|",
    ]
    for out in outputs:
        if out["category"] in SKIP_RAGAS_CATEGORIES:
            answer_trunc = out["answer"].replace("\n", " ")[:100]
            lines.append(
                f"| {out['id']} | {out['category']} | {out['confidence_flag']} | {answer_trunc} |"
            )

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote summary to {summary_path}")
    print(f"Wrote per-row scores to {_scores_path()}")
    print("\n=== Aggregate scores ===")
    for metric, val in means.items():
        print(f"  {metric}: {val:.3f}")


async def _run_pipeline_phase(rows: list[dict]) -> list[dict]:
    """The entire async phase (DB + pipeline calls) lives in its own
    asyncio.run(), start to finish. ragas's evaluate() below is a
    synchronous call that manages its own event loop internally --
    calling it while we're still inside our own running loop would mean
    relying on ragas's nest_asyncio patching to nest loops correctly.
    That's supported (allow_nest_asyncio defaults True) but avoidable, so
    it's avoided: the async phase fully finishes and its loop is torn
    down before evaluate() ever runs."""
    adapter, entity_resolver, db_client = await _build_pipeline()
    try:
        outputs = await _run_pipeline(adapter, entity_resolver, rows)
    finally:
        await db_client.close()
    return outputs


def main() -> None:
    t0 = time.time()
    rows = _load_questions()
    print(f"Loaded {len(rows)} eval questions from {EVAL_CSV}")

    outputs = asyncio.run(_run_pipeline_phase(rows))

    dataset, scored_ids = _build_ragas_dataset(outputs)
    print(f"\n{len(scored_ids)} rows eligible for RAGAS scoring "
          f"(excluded categories: {sorted(SKIP_RAGAS_CATEGORIES)})")

    # Diagnostic override: RAGAS_MAX_ROWS lets a small slice run through
    # the judge phase to see the REAL error before committing to a full
    # run again. Unset/absent = no limit, full run.
    _max_rows_env = os.getenv("RAGAS_MAX_ROWS")
    if _max_rows_env:
        _max_rows = int(_max_rows_env)
        dataset.samples = dataset.samples[:_max_rows]
        scored_ids = scored_ids[:_max_rows]
        print(f"RAGAS_MAX_ROWS={_max_rows} set -- truncating to first "
              f"{len(scored_ids)} rows for a diagnostic run.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scores_path = _scores_path()
    existing_scores = _load_existing_scores(scores_path)
    if existing_scores:
        print(f"Resuming judge phase: {len(existing_scores)}/{len(scored_ids)} rows "
              f"already fully scored in a previous run, will be reused as-is.")

    id_to_sample = dict(zip(scored_ids, dataset.samples))
    pending_ids = [i for i in scored_ids if i not in existing_scores]
    accumulated: dict[str, dict] = dict(existing_scores)

    if not pending_ids:
        print("All eligible rows already fully scored -- skipping the judge phase entirely.")
    else:
        judge_llm, embeddings = _build_judge_and_embeddings()
        SingleTurnSample, EvaluationDataset = _get_sample_and_dataset_classes()
        total_batches = (len(pending_ids) + BATCH_ROWS - 1) // BATCH_ROWS
        print(f"Running RAGAS evaluation with judge={JUDGE_MODEL} "
              f"({len(pending_ids)} rows pending, {total_batches} batch(es) of "
              f"up to {BATCH_ROWS} rows) ...")

        quota_stopped = False
        for start in range(0, len(pending_ids), BATCH_ROWS):
            batch_ids = pending_ids[start:start + BATCH_ROWS]
            batch_samples = [id_to_sample[i] for i in batch_ids]
            batch_dataset = EvaluationDataset(samples=batch_samples)
            batch_num = start // BATCH_ROWS + 1
            print(f"\n--- Batch {batch_num}/{total_batches}: {len(batch_ids)} row(s) ---")

            try:
                # raise_exceptions=True here (unlike the old single-shot
                # call): a real failure should surface immediately and
                # distinctly rather than degrade to a silent NaN, since
                # main() now needs to tell a dead daily quota apart from
                # an ordinary bug. The cost of a raised exception is
                # bounded to this one batch's rows, not the whole run,
                # because every earlier batch was already checkpointed
                # to scores_path below.
                batch_result = _run_ragas(batch_dataset, judge_llm, embeddings,
                                           raise_exceptions=True)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                quota_markers = (
                    "RESOURCE_EXHAUSTED", "429", "quota", "ResourceExhausted",
                    "GenerateRequestsPerDayPerProjectPerModel",
                )
                if any(marker.lower() in msg.lower() for marker in quota_markers):
                    new_this_run = len(accumulated) - len(existing_scores)
                    print(f"\n!! Quota/rate-limit error mid-batch: {msg[:400]}")
                    print(f"Stopping here. {new_this_run} new row(s) scored this run "
                          f"(on top of {len(existing_scores)} reused from before), "
                          f"{len(accumulated)}/{len(scored_ids)} total. This is very "
                          f"likely today's free-tier request quota "
                          f"(GenerateRequestsPerDayPerProjectPerModel-FreeTier, confirmed "
                          f"at 500/day for {JUDGE_MODEL} on 2026-09-01/02) rather than a "
                          f"bug -- rerun this exact command after it resets (Gemini "
                          f"free-tier daily quotas reset at midnight Pacific time) and it "
                          f"will pick up exactly where this left off, skipping every row "
                          f"already checkpointed below.")
                    quota_stopped = True
                    break
                # A timeout is not a reason to end the run. Every earlier
                # batch is already checkpointed, and one slow row should cost
                # that row, not the remaining batches. Skip and continue --
                # the row stays unscored and is picked up on the next run.
                if isinstance(exc, (asyncio.TimeoutError, asyncio.CancelledError)) or \
                        "TimeoutError" in type(exc).__name__ or "timeout" in msg.lower():
                    print(f"\n!! Batch {batch_num} timed out ({msg[:200]}). "
                          f"Skipping these row(s) and continuing; they stay unscored "
                          f"and will be retried on the next run.")
                    continue

                print(f"\n!! Unexpected error mid-batch (not quota-shaped): {msg[:600]}")
                raise

            batch_df = batch_result.to_pandas()
            batch_df.insert(0, "id", batch_ids)
            for _, row in batch_df.iterrows():
                accumulated[row["id"]] = row.to_dict()

            # Checkpoint after every batch -- the actual fix for the
            # 2026-09-01/02 failures: a later batch hitting the daily
            # quota no longer costs this batch's, or any earlier
            # batch's, already-completed judge calls.
            ordered_ids = [i for i in scored_ids if i in accumulated]
            merged_df = pd.DataFrame([accumulated[i] for i in ordered_ids])
            merged_df.to_csv(scores_path, index=False)
            print(f"Checkpointed {len(accumulated)}/{len(scored_ids)} scored rows "
                  f"to {scores_path}")

        if not quota_stopped:
            print("\nAll pending rows scored -- judge phase complete.")

    final_ids = [i for i in scored_ids if i in accumulated]
    scores_df = pd.DataFrame([accumulated[i] for i in final_ids]) if final_ids else pd.DataFrame()

    _write_summary(outputs, scores_df, final_ids)
    print(f"\nDone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
