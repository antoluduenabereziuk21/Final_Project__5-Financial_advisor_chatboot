from __future__ import annotations

import os

_LLM_PROVIDER: str | None = None  # set by configure()


def configure(provider: str | None = "groq") -> None:
    global _LLM_PROVIDER
    _LLM_PROVIDER = provider


def _build_prompt(question: str, sources: list[dict]) -> str:
    context_parts = []
    for i, s in enumerate(sources, 1):
        header = f"[{i}] {s.get('company', '?')} ({s.get('ticker', '?')}) "
        header += f"FY{s.get('fiscal_year', '?')} — {s.get('canonical_section', '?')}"
        # Use the full retrieved chunk as grounding context for the LLM.
        # text_snippet remains as a compatibility fallback for older callers.
        chunk_content = s.get("content") or s.get("text_snippet", "")
        context_parts.append(f"{header}\n{chunk_content}")

    context = "\n\n".join(context_parts)
    return (
        "Eres un asistente financiero experto en análisis de reportes 10-K y 20-F.\n\n"
        "Contexto extraído de reportes financieros:\n"
        f"{context}\n\n"
        "Pregunta del usuario:\n"
        f"{question}\n\n"
        "Instrucciones:\n"
        "- Responde basándote exclusivamente en el contexto proporcionado.\n"
        "- Si el contexto no contiene suficiente información para responder, indícalo.\n"
        "- Cuando cites cifras, menciona la empresa y el año fiscal.\n"
        "- Si comparas empresas con distintos accounting_standard (US-GAAP vs IFRS), "
        "advierte explícitamente que las cifras pueden no ser directamente comparables.\n"
        "- No des consejos de inversión ni opiniones subjetivas.\n"
        "Respuesta:"
    )


def _compute_confidence_flag(
    sources: list[dict], question: str
) -> str:
    if not sources:
        return "entity_not_found"

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
    # fine", it's "unchecked". If any source feeding this answer is unverified,
    # don't report "ok" as if the company attribution were confirmed correct.
    # (True/confirmed-mismatch sources are excluded upstream at embedding time
    # and shouldn't reach here at all -- this only catches the unchecked case.)
    if any(s.get("company_name_mismatch") is None for s in sources):
        return "low_confidence"

    return "ok"


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
        prompt = _build_prompt(question, sources)
        return _fallback_generate(prompt, sources, confidence_flag)

    # Await the asynchronous LLM provider before returning its result.
    return await _llm_generate(question, sources, confidence_flag)


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

    prompt = _build_prompt(question, sources)
    return _fallback_generate(prompt, sources, flag)


async def _groq_generate(
    question: str, sources: list[dict], flag: str
) -> tuple[str, str]:
    import groq

    prompt = _build_prompt(question, sources)
    client = groq.AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    response = await client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    answer = response.choices[0].message.content or ""
    return answer, flag
