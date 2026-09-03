from __future__ import annotations

import logging
import os

_LLM_PROVIDER: str | None = None  # set by configure()


def configure(provider: str | None = "groq") -> None:
    global _LLM_PROVIDER
    _LLM_PROVIDER = provider


_SYSTEM = (
    "You are a financial analyst assistant. You work only from excerpts of SEC "
    "annual filings (10-K / 20-F / 40-F).\n"
    "Rules:\n"
    "1. Use only the CONTEXT. If it does not contain the answer, reply with the "
    "single token NOT_IN_CONTEXT followed by one short sentence naming what is missing.\n"
    "2. Always answer in English, whatever language the question is in.\n"
    "3. Reproduce figures exactly as written in the context, with their units and "
    "scale. Name the company and fiscal year for every figure and cite the excerpt "
    "number, e.g. [2].\n"
    "4. If figures come from different accounting standards (US-GAAP vs IFRS), say "
    "they may not be directly comparable.\n"
    "5. Never give investment advice, recommendations, price targets or opinions. "
    "Report data only.\n"
    "6. Be concise. No preamble."
)

# Flag-conditional lines. Only the line for the active flag is sent, so the
# prompt stays short: the system block above is fixed and identical on every
# call, and only one NOTES line is ever appended.
_FLAG_NOTES = {
    "unverified_source": (
        "At least one excerpt has a company attribution that is still being "
        "verified. Answer normally, but do not present the company identity as "
        "confirmed."
    ),
    "low_confidence": (
        "Retrieval confidence for this question is weak: the excerpts may be "
        "only loosely related to the question. Answer only what the excerpts "
        "directly support, and state up front that the supporting evidence is "
        "weak. Prefer NOT_IN_CONTEXT over inference."
    ),
}

# Sentinel the model is asked to emit when the context does not answer the
# question (system rule 1). Machine-checkable, unlike guessing at prose
# ("the context does not contain..."), which is what left 45/70 rows in the
# 2026-09-02 eval labelled confidence_flag="ok" while actually being refusals.
_NOT_IN_CONTEXT = "NOT_IN_CONTEXT"

_REFUSAL_PATTERNS = (
    "not contain", "does not include", "no se incluye", "no contiene",
    "not possible to determine", "cannot be determined", "no encontr",
    "insufficient information", "no information about",
)


def _looks_like_refusal(answer: str) -> bool:
    """Sentinel first, prose second. The prose fallback exists because the
    model does not always comply with rule 1, and a refusal mislabelled as a
    real answer poisons both the confidence flag and every RAGAS metric
    scored on that row."""
    a = answer.strip()
    if _NOT_IN_CONTEXT in a:
        return True
    head = a[:400].lower()
    return any(p in head for p in _REFUSAL_PATTERNS)


def _strip_sentinel(answer: str) -> str:
    if _NOT_IN_CONTEXT not in answer:
        return answer
    rest = answer.replace(_NOT_IN_CONTEXT, "", 1).lstrip(" \n:.-")
    return ("The retrieved filing excerpts do not contain this information. "
            + rest).strip()


def _build_messages(question: str, sources: list[dict], flag: str | None = None) -> list[dict]:
    context_parts = []
    for i, s in enumerate(sources, 1):
        header = f"[{i}] {s.get('company', '?')} ({s.get('ticker', '?')}) "
        header += f"FY{s.get('fiscal_year', '?')} - {s.get('canonical_section', '?')}"
        # Full retrieved chunk as grounding context; text_snippet is a
        # compatibility fallback for older callers.
        chunk_content = s.get("content") or s.get("text_snippet", "")
        context_parts.append(f"{header}\n{chunk_content}")

    user = "CONTEXT\n" + "\n\n".join(context_parts) + f"\n\nQUESTION\n{question}"
    note = _FLAG_NOTES.get(flag or "")
    if note:
        user += f"\n\nNOTE\n{note}"
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]


def _build_prompt(question: str, sources: list[dict], flag: str | None = None) -> str:
    """Compatibility shim for callers that still want a single string."""
    return "\n\n".join(m["content"] for m in _build_messages(question, sources, flag))


_SUBJECTIVE_MARKERS = [
    # es
    "mejor", "recomendarías", "recomiendas", "debería", "opinión",
    "preferirías", "conviene", "vale la pena", "qué tan riesgoso",
    "invertir en", "comprar acciones",
    # en
    "should i", "would you recommend", "do you recommend", "is it worth",
    "good investment", "good buy", "good long-term", "good long term",
    "worth buying", "worth investing", "what would you recommend",
    "advise", "your opinion", "how risky",
    ]


def _is_subjective(question: str) -> bool:
    q = question.lower()
    return any(m in q for m in _SUBJECTIVE_MARKERS)


def _compute_confidence_flag(
    sources: list[dict], question: str
) -> str:
    # Subjective questions are refused BEFORE the empty-retrieval check.
    # "Should I invest in Apple?" returning entity_not_found instead of
    # subjective_no_verdict (2026-09-02 run, ids 62/63) made a compliance
    # guardrail conditional on retrieval happening to succeed. Whether the
    # question asks for investment advice has nothing to do with retrieval.
    if _is_subjective(question):
        return "subjective_no_verdict"

    if not sources:
        return "entity_not_found"

    # NOTE: 0.4 is an uncalibrated constant carried over from the original
    # implementation -- not validated against any labeled query set. Treat
    # any product decision that depends on this exact threshold (e.g. hard
    # blocking) as provisional until that calibration happens.
    # Subjective check moved AHEAD of the low_confidence score check
    # (2026-09-02). Previously a subjective question that happened to
    # retrieve weakly returned low_confidence and never reached the
    # subjective refusal, so the compliance guardrail was conditional on
    # retrieval quality -- which has nothing to do with whether the
    # question asks for investment advice.
    #
    # Markers were Spanish-only, which is why all three English
    # subjective_gate_bypass rows (ids 36/37/38) in the 2026-09-02 run
    # sailed through with flag="ok" and got a full generated answer. The
    # category is named "bypass" and it was, in fact, bypassing.
    max_score = max(s["relevance_score"] for s in sources)
    if max_score < 0.4:
        return "low_confidence"

    # company_name_mismatch is NULL for a source whose folder-derived company
    # was never cross-checked against the cover-page registrant name (~19.5%
    # of the corpus, per rag/ingestion/RESULTS.md) -- NULL is not "confirmed
    # fine", it's "unchecked". This is deliberately a distinct flag from
    # low_confidence: an unverified attribution says nothing about retrieval
    # relevance, so it must not be treated (or gated) the same way as a weak
    # match. (True/confirmed-mismatch sources are excluded upstream at
    # embedding time and shouldn't reach here at all -- this only catches the
    # unchecked case.)
    #
    # Scoped to the top-scoring source's company, not the whole retrieved
    # set. Confirmed real on 2026-08-21: with retrieval unfiltered by
    # ticker/company (finding 2.6), top-k routinely includes chunks from
    # unrelated companies that share vocabulary with the question -- a
    # question about Antares Pharma's LEO Pharma payment also retrieved an
    # unrelated Argenx chunk (which separately, coincidentally, has its own
    # LEO Pharma agreement) and an unrelated Ascendis Pharma chunk, both
    # with company_name_mismatch IS NULL and neither cited in the answer.
    # Checking any(...) over the whole set let those uncited, unrelated
    # chunks flag a fully clean, correctly-sourced answer as unverified.
    # Scoping to same-company sources means only chunks that could actually
    # have grounded the answer affect this flag. This does not require an
    # LLM change -- the flag is computed before generation and the
    # disclaimer is appended after it regardless of what the model wrote
    # (see _with_unverified_source_notice), so there is no prompt lever
    # here at all.
    top_source = max(sources, key=lambda s: s["relevance_score"])
    same_company_sources = [
        s for s in sources if s.get("company") == top_source.get("company")
    ]
    if any(s.get("company_name_mismatch") is None for s in same_company_sources):
        return "unverified_source"

    return "ok"


_LOW_CONFIDENCE_NOTICE = (
    "Note: retrieval confidence for this question was low (best excerpt "
    "similarity below threshold). The supporting evidence may be only loosely "
    "related to the question."
)


def _with_low_confidence_notice(answer: str) -> str:
    if _LOW_CONFIDENCE_NOTICE in answer:
        return answer
    return f"{answer}\n\n{_LOW_CONFIDENCE_NOTICE}"


_UNVERIFIED_SOURCE_NOTICE = (
    "Note: this answer relies on at least one source whose company "
    "attribution has not completed verification (source in verification "
    "process). Treat the named company/ticker as provisional."
)


def _with_unverified_source_notice(answer: str) -> str:
    # Code-enforced, not left to the LLM's discretion: the prompt also asks
    # the model to hedge (see _build_prompt), but that's a request, not a
    # guarantee. This append always runs when the flag is set, regardless of
    # whether the model complied.
    if _UNVERIFIED_SOURCE_NOTICE in answer:
        return answer
    return f"{answer}\n\n{_UNVERIFIED_SOURCE_NOTICE}"


async def generate(
    question: str, sources: list[dict]
) -> tuple[str, str]:
    confidence_flag = _compute_confidence_flag(sources, question)

    if confidence_flag == "entity_not_found":
        return (
            "I could not find that company or period in the available filings.",
            confidence_flag,
        )

    if confidence_flag == "subjective_no_verdict":
        return (
            "I can't give a recommendation or an opinion on that. I can show you "
            "the figures in the filings so you can judge for yourself.",
            confidence_flag,
        )

    if _LLM_PROVIDER is None:
        prompt = _build_prompt(question, sources, confidence_flag)
        answer, flag = _fallback_generate(prompt, sources, confidence_flag)
    else:
        answer, flag = await _llm_generate(question, sources, confidence_flag)

    # Post-hoc: the model said the context does not answer the question. The
    # flag must reflect that, otherwise a refusal is reported as a successful
    # answer -- 45 of 70 rows in the 2026-09-02 run. Overrides ok /
    # unverified_source / low_confidence alike: none of them are true of a
    # non-answer.
    if _looks_like_refusal(answer):
        return _strip_sentinel(answer), "no_answer_in_context"

    # Code-enforced banners, not left to the model's discretion: the prompt
    # also asks it to hedge (see _FLAG_NOTES), but that is a request, not a
    # guarantee.
    if flag == "unverified_source":
        answer = _with_unverified_source_notice(answer)
    elif flag == "low_confidence":
        answer = _with_low_confidence_notice(answer)

    return answer, flag


def _fallback_generate(
    prompt: str, sources: list[dict], flag: str
) -> tuple[str, str]:
    if flag == "low_confidence":
        return (
            "I am not confident enough to answer precisely from the retrieved excerpts.",
            flag,
        )
    return ("[No LLM provider configured - simulated response]", flag)


async def _llm_generate(
    question: str, sources: list[dict], flag: str
) -> tuple[str, str]:
    if _LLM_PROVIDER == "groq":
        return await _groq_generate(question, sources, flag)

    prompt = _build_prompt(question, sources, flag)
    return _fallback_generate(prompt, sources, flag)


async def _groq_generate(
    question: str, sources: list[dict], flag: str
) -> tuple[str, str]:
    import groq

    messages = _build_messages(question, sources, flag)
    client = groq.AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    # temperature 0.0 by default (was 0.3): a non-zero temperature makes eval
    # runs non-reproducible and folds sampling noise into every RAGAS metric.
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.0"))
    # max_tokens is REQUIRED, not cosmetic. Groq charges the daily token
    # budget against limit + requested, and "requested" includes the
    # completion reservation. On 2026-09-02 an uncapped call reported
    # "Used 171065, Requested 91950" against a 200000 TPD limit and killed
    # the run at row 60/68, even though actual usage was only ~2.9k
    # tokens/row. Capping the reservation is what makes 68 rows fit.
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "800"))
    try:
        response = await client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        # Previously this propagated to a bare FastAPI 500 with no logging of
        # which question failed, and in the eval harness it killed the run.
        logging.getLogger(__name__).warning(
            "groq generation failed (%s): %s", type(exc).__name__, exc
        )
        return (
            "The answer service is temporarily unavailable. Please retry.",
            "generation_error",
        )
    answer = response.choices[0].message.content or ""
    return answer, flag
