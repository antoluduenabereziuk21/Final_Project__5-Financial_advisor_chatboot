from __future__ import annotations

import asyncio

from app.services.rag_service import RAGService


class DummyRootAdapter:
    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict | None = None,
        top_k: int = 5,
    ) -> dict:
        return {
            "answer": "respuesta de prueba",
            "confidence_flag": "ok",
            "sources": [
                {
                    "chunk_id": "chunk-1",
                    "company": "Acme",
                    "ticker": "ACM",
                    "fiscal_year": 2024,
                    "form_type": "10-K",
                    "accounting_standard": "US-GAAP",
                    "canonical_section": "Balance Sheet",
                    "source_file": "acme.pdf",
                    "page_start": 10,
                    "page_end": 12,
                    "relevance_score": 0.91,
                    "text_snippet": "snippet",
                }
            ],
            "retrieval_meta": {
                "filters_applied": {
                    "ticker": "ACM",
                    "company": "Acme",
                    "fiscal_year": 2024,
                },
                "chunks_considered": 1,
                "model": "all-MiniLM-L6-v2",
            },
        }


def test_rag_service_uses_root_contract_fields() -> None:
    async def run_test() -> dict:
        service = RAGService(adapter=DummyRootAdapter())
        return await service.generate_answer(
            question="¿Qué pasó en 2024?",
            conversation_history=[],
            filters={"ticker": "ACM", "company": "Acme", "fiscal_year": 2024},
            top_k=3,
        )

    result = asyncio.run(run_test())

    assert result["confidence_flag"] == "ok"
    assert result["sources"][0]["chunk_id"] == "chunk-1"
    assert result["retrieval_meta"]["filters_applied"]["ticker"] == "ACM"
    assert result["retrieval_meta"]["model"] == "all-MiniLM-L6-v2"
