from __future__ import annotations

from typing import Any

from app.services.rag_service import RootRAGAdapter

from rag.embeddings.generate import embed_text
from rag.llm.generator import generate
from rag.retrieval.retriever import VectorSearchRepository, retrieve


class RootRAGAdapterImpl:
    """Bridge the backend ChatService with the shared RAG pipeline.

    The adapter depends on the VectorSearchRepository protocol instead of a
    concrete database implementation. This allows the existing /api/chat flow
    to work with either PostgreSQL/pgvector or Supabase HTTPS/RPC.
    """

    def __init__(self, repo: VectorSearchRepository) -> None:
        self._repo = repo

    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        filters = filters or {}
        ticker = filters.get("ticker")
        company = filters.get("company")
        fiscal_year = filters.get("fiscal_year")

        sources, retrieval_meta = await retrieve(
            repo=self._repo,
            question=question,
            ticker=ticker,
            company=company,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )

        answer, confidence_flag = await generate(question, sources)

        return {
            "answer": answer,
            "confidence_flag": confidence_flag,
            "sources": sources,
            "retrieval_meta": retrieval_meta,
        }
