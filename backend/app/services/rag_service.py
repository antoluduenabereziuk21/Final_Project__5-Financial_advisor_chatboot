from __future__ import annotations

from typing import Any, Protocol


class RootRAGAdapter(Protocol):
    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        ...


class RAGService:
    def __init__(self, adapter: RootRAGAdapter | None = None) -> None:
        self._adapter = adapter

    async def generate_answer(
        self,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        if self._adapter is None:
            # No RAG adapter wired up -- neither the Postgres nor the Supabase
            # vector backend connected at startup (see backend/app/main.py
            # lifespan). There is no real retrieval happening, so we must not
            # fabricate a source or a citation to paper over that: doing so
            # previously produced a fake-but-plausible "Apple Annual Report
            # 2025" citation regardless of what was actually asked. Report the
            # outage plainly instead.
            return {
                "answer": (
                    "The retrieval system is currently unavailable, so I can't "
                    "provide a data-backed answer right now. Please try again "
                    "later."
                ),
                "confidence_flag": "system_unavailable",
                "sources": [],
                "retrieval_meta": {
                    "filters_applied": filters or {},
                    "chunks_considered": 0,
                    "model": "all-MiniLM-L6-v2",
                },
            }

        return await self._adapter.generate_answer(
            question=question,
            conversation_history=conversation_history,
            filters=filters,
            top_k=top_k,
        )
