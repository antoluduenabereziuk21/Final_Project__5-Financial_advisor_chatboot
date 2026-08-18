from __future__ import annotations

from typing import Protocol

from rag.embeddings.generate import embed_text
from rag.vector_store.models import SearchParams, SearchResult


class VectorSearchRepository(Protocol):
    async def search_similar(
        self,
        params: SearchParams,
    ) -> list[SearchResult]:
        ...


async def retrieve(
    repo: VectorSearchRepository,
    question: str,
    ticker: list[str] | None = None,
    company: list[str] | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> tuple[list[dict], dict]:
    """Generate the question embedding and return the most relevant chunks."""

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

    for result in results:
        sources.append(
            {
                "chunk_id": result.id,
                "company": result.company,
                "ticker": result.ticker,
                "fiscal_year": result.fiscal_year,
                "form_type": result.form_type,
                "accounting_standard": result.accounting_standard,
                "canonical_section": result.canonical_section,
                "source_file": result.source_file,
                "page_start": result.page_start,
                "page_end": result.page_end,
                "relevance_score": result.similarity,

                # Full chunk for the LLM context.
                "content": result.content,

                # Short preview for API/UI source display.
                "text_snippet": result.content[:300],

                "company_name_mismatch": result.company_name_mismatch,
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
