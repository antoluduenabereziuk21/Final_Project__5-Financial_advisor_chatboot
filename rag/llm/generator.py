from __future__ import annotations

import os

_LLM_PROVIDER: str | None = None  # set by configure()


def configure(provider: str | None = "groq") -> None:
    global _LLM_PROVIDER
    _LLM_PROVIDER = provider


def _build_prompt(question: str, sources: list[dict], flag: str | None = None) -> str:
    context_parts = []
    for i, s in enumerate(sources, 1):
        header = f"[{i}] {s.get('company', '?')} ({s.get('ticker', '?')}) "
        header += f"FY{s.get('fiscal_year', '?')} — {s.get('canonical_section', '?')}"
        # Use the full retrieved chunk as grounding context for the LLM.
        # text_snippet remains as a compatibility fallback for older callers.
        chunk_content = s.get("content") or s.get("text_snippet", "")
        context_parts.append(f"{header}\n{chunk_content}")

    context = "\n\n".join(context_parts)

    instructions = [
        "- Responde basándote exclusivamente en el contexto proporcionado.",
        "- Si el contexto no contiene suficiente información para responder, indícalo.",
        "- Cuando cites cifras, menciona la empresa y el año fiscal.",
        "- Si comparas empresas con distintos accounting_standard (US-GAAP vs IFRS), "
        "advierte explícitamente que las cifras pueden no ser directamente comparables.",
        "- No des consejos de inversión ni opiniones subjetivas.",
    ]
    if flag == "unverified_source":
        instructions.append(
            "- Al menos una fuente usada aquí tiene su atribución de empresa "
            "todavía en proceso de verificación (no confirmada como correcta "
            "ni como incorrecta). Responde con normalidad, pero evita "
            "presentar la identidad de la empresa citada como un hecho "
            "100% confirmado."
        )

    return (
        "Eres un asistente financiero experto en análisis de reportes 10-K y 20-F.\n\n"
        "Contexto extraído de reportes financieros:\n"
        f"{context}\n\n"
        "Pregunta del usuario:\n"
        f"{question}\n\n"
        "Instrucciones:\n" + "\n".join(instructions) + "\n"
        "Respuesta:"
    )


def _compute_confidence_flag(
    sources: list[dict], question: str
) -> str:
    if not sources:
        return "entity_not_found"

    # NOTE: 0.4 is an uncalibrated constant carried over from the original
    # implementation -- not validated against any labeled query set. Treat
    # any product decision that depends on this exact threshold (e.g. hard
    # blocking) as provisional until that calibration happens.
    max_score = max(s["relevance_score"] for s in sources)
    if max_score < 0.4:
        return "low_confidence"

    subjective_markers = [
        "mejor",
        "recomendarías",
        "debería",
        "opinión",
        "preferirías",
        "cuál es la mejor",
    ]
    q_lower = question.lower()
    if any(m in q_lower for m in subjective_markers):
        return "subjective_no_verdict"

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
            "No encontré información sobre esa empresa o período en los reportes disponibles.",
            confidence_flag,
        )

    if confidence_flag == "subjective_no_verdict":
        return (
            "No tengo una respuesta concluyente para esa pregunta. "
            "Puedo presentarte los datos disponibles para que tú mismo evalúes.",
            confidence_flag,
        )

    if _LLM_PROVIDER is None:
        prompt = _build_prompt(question, sources, confidence_flag)
        answer, flag = _fallback_generate(prompt, sources, confidence_flag)
    else:
        # Await the asynchronous LLM provider before returning its result.
        answer, flag = await _llm_generate(question, sources, confidence_flag)

    if flag == "unverified_source":
        answer = _with_unverified_source_notice(answer)

    return answer, flag


def _fallback_generate(
    prompt: str, sources: list[dict], flag: str
) -> tuple[str, str]:
    if flag == "low_confidence":
        return (
            "No tengo suficiente certeza para responder con precisión basándome en los fragmentos recuperados.",
            flag,
        )
    return ("[Modo sin LLM configurado — respuesta simulada]", flag)


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

    prompt = _build_prompt(question, sources, flag)
    client = groq.AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    response = await client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    answer = response.choices[0].message.content or ""
    return answer, flag
