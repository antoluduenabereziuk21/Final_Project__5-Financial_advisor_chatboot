from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.rag.types import DocumentChunk


class Retriever(Protocol):
    async def similarity_search(
        self,
        query_embedding: Sequence[float],
        conversation_history: Sequence[dict[str, str]],
        top_k: int = 4,
    ) -> list[DocumentChunk]:
        ...


class MockRetriever:
    async def similarity_search(
        self,
        query_embedding: Sequence[float],
        conversation_history: Sequence[dict[str, str]],
        top_k: int = 4,
    ) -> list[DocumentChunk]:
        # This is the seam where Pinecone, FAISS or another vector store backed
        # retriever should be connected in production.
        if query_embedding and query_embedding[0] >= 7:
            return [
                DocumentChunk(
                    id="apple-annual-report-2025",
                    content=(
                        "Apple mantiene una posición de liquidez sólida, fuerte flujo de caja "
                        "operativo y márgenes estables en su negocio principal."
                    ),
                    score=0.92,
                    metadata={
                        "title": "Apple Annual Report 2025",
                        "source": "annual_report",
                        "year": 2025,
                    },
                ),
                DocumentChunk(
                    id="apple-investor-relations-summary",
                    content=(
                        "La compañía continúa apoyándose en servicios, hardware premium y "
                        "recompras de acciones para sostener valor para el accionista."
                    ),
                    score=0.84,
                    metadata={
                        "title": "Apple Investor Relations Summary",
                        "source": "investor_relations",
                    },
                ),
            ][:top_k]

        return [
            DocumentChunk(
                id="general-financial-market-overview",
                content=(
                    "No se encontraron documentos específicos, pero el sistema puede "
                    "responder con contexto genérico mientras se integra el índice real."
                ),
                score=0.5,
                metadata={
                    "title": "General Financial Market Overview",
                    "source": "fallback",
                },
            )
        ][:top_k]

    async def retrieve(
        self,
        question: str,
        query_embedding: Sequence[float],
        conversation_history: Sequence[dict[str, str]],
    ) -> list[DocumentChunk]:
        return await self.similarity_search(query_embedding, conversation_history)
