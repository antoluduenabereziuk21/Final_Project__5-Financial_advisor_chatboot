from __future__ import annotations

from typing import Any

from app.services.rag_service import RootRAGAdapter

from rag.embeddings.generate import embed_text
from rag.llm.generator import generate
from rag.retrieval.retriever import retrieve
from rag.vector_store.repository import VectorRepository


class RootRAGAdapterImpl:
    """Bridges the backend ChatService with the real rag/ modules.

    Conforms to the RootRAGAdapter protocol expected by RAGService.
    """

    def __init__(self, repo: VectorRepository) -> None:
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
