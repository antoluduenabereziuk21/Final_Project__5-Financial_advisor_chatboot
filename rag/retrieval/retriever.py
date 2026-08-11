from __future__ import annotations

from rag.embeddings.generate import embed_text
from rag.vector_store.models import SearchParams
from rag.vector_store.repository import VectorRepository


async def retrieve(
    repo: VectorRepository,
    question: str,
    ticker: list[str] | None = None,
    company: list[str] | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> tuple[list[dict], dict]:
    """Embed la pregunta, aplica filtros tipados (ticker / company /
    fiscal_year) y devuelve sources[] con la estructura del contrato."""
    query_embedding = embed_text(question)

    params = SearchParams(
        query_embedding=query_embedding,
        top_k=top_k,
        ticker=ticker,
        company=company,
        fiscal_year=fiscal_year,
    )
    results = await repo.search_similar(params)

    sources = []
    for r in results:
        sources.append(
            {
                "chunk_id": r.id,
                "company": r.company,
                "ticker": r.ticker,
                "fiscal_year": r.fiscal_year,
                "form_type": r.form_type,
                "accounting_standard": r.accounting_standard,
                "canonical_section": r.canonical_section,
                "source_file": r.source_file,
                "page_start": r.page_start,
                "page_end": r.page_end,
                "relevance_score": r.similarity,
                "text_snippet": r.content[:300],
                "company_name_mismatch": r.company_name_mismatch,
            }
        )

    filters_applied = {}
    if ticker:
        filters_applied["ticker"] = ticker
    if company:
        filters_applied["company"] = company
    if fiscal_year is not None:
        filters_applied["fiscal_year"] = fiscal_year

    retrieval_meta = {
        "filters_applied": filters_applied or None,
        "chunks_considered": len(results),
        "model": "all-MiniLM-L6-v2",
    }

    return sources, retrieval_meta
