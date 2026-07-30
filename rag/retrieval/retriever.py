from __future__ import annotations

from rag.embeddings.generate import embed_text
from rag.vector_store.models import SearchParams
from rag.vector_store.repository import VectorRepository


def _build_metadata_filter(
    ticker: list[str] | None,
    company: list[str] | None,
    fiscal_year: int | None,
) -> dict | None:
    parts: dict[str, object] = {}
    if ticker:
        parts["ticker"] = {"$in": ticker} if len(ticker) > 1 else ticker[0]
    if company:
        parts["company"] = {"$in": company} if len(company) > 1 else company[0]
    if fiscal_year is not None:
        parts["fiscal_year"] = fiscal_year

    # Build pgvector JSONB filter — needs to match how metadata is stored
    # ticker and company are flat strings, fiscal_year is int; JSONB @> works
    # with exact matches. For $in semantics we do OR in post-filtering.
    filters: dict | None = None
    if "ticker" in parts and isinstance(parts["ticker"], str):
        filters = {**(filters or {}), "ticker": parts["ticker"]}
    if "company" in parts and isinstance(parts["company"], str):
        filters = {**(filters or {}), "company": parts["company"]}
    if "fiscal_year" in parts:
        filters = {**(filters or {}), "fiscal_year": parts["fiscal_year"]}

    return filters


async def retrieve(
    repo: VectorRepository,
    question: str,
    ticker: list[str] | None = None,
    company: list[str] | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> tuple[list[dict], dict]:
    query_embedding = embed_text(question)
    metadata_filter = _build_metadata_filter(ticker, company, fiscal_year)

    params = SearchParams(
        query_embedding=query_embedding,
        top_k=top_k,
        metadata_filter=metadata_filter,
    )
    results = await repo.search_similar(params)

    # Post-filter for $in semantics (JSONB @> doesn't natively support $in)
    filtered = _post_filter(
        results, ticker=ticker, company=company, fiscal_year=fiscal_year
    )

    sources = []
    for r in filtered:
        meta = r.metadata
        sources.append(
            {
                "chunk_id": r.id,
                "company": meta.get("company"),
                "ticker": meta.get("ticker"),
                "fiscal_year": meta.get("fiscal_year"),
                "form_type": meta.get("form_type"),
                "accounting_standard": meta.get("accounting_standard"),
                "canonical_section": meta.get("canonical_section"),
                "source_file": meta.get("source_file"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "relevance_score": r.similarity,
                "text_snippet": r.content[:300],
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
        "chunks_considered": len(filtered),
        "model": "all-MiniLM-L6-v2",
    }

    return sources, retrieval_meta


def _post_filter(
    results: list,
    ticker: list[str] | None = None,
    company: list[str] | None = None,
    fiscal_year: int | None = None,
) -> list:
    if not any([ticker, company, fiscal_year is not None]):
        return results

    filtered = []
    for r in results:
        meta = r.metadata
        if ticker and meta.get("ticker") not in ticker:
            continue
        if company and meta.get("company") not in company:
            continue
        if fiscal_year is not None and meta.get("fiscal_year") != fiscal_year:
            continue
        filtered.append(r)
    return filtered
