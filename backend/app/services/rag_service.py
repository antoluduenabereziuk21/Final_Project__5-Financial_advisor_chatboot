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
            return {
                "answer": "RAG root adapter is not configured yet.",
                "confidence_flag": "low_confidence",
                "sources": [
                    {
                        "chunk_id": "fallback-chunk",
                        "company": "unknown",
                        "ticker": "UNKNOWN",
                        "fiscal_year": None,
                        "form_type": None,
                        "accounting_standard": None,
                        "canonical_section": None,
                        "source_file": None,
                        "page_start": None,
                        "page_end": None,
                        "relevance_score": 0.0,
                        "text_snippet": "Fallback source while the root RAG adapter is not wired.",
                    }
                ],
                "retrieval_meta": {
                    "filters_applied": filters or {},
                    "chunks_considered": 1,
                    "model": "all-MiniLM-L6-v2",
                },
            }

        return await self._adapter.generate_answer(
            question=question,
            conversation_history=conversation_history,
            filters=filters,
            top_k=top_k,
        )
