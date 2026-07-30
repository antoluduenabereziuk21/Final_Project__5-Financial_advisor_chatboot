from __future__ import annotations

from collections.abc import Sequence

from app.rag.embeddings import EmbeddingService
from app.rag.llm import LLMService
from app.rag.prompt_builder import MockPromptBuilder, PromptBuilder
from app.rag.retriever import Retriever
from app.rag.types import RAGContext, RAGResponse, RAGSource


class RAGChain:
    def __init__(
        self,
        retriever: Retriever,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._retriever = retriever
        self._embedding_service = embedding_service
        self._llm_service = llm_service
        self._prompt_builder = prompt_builder or MockPromptBuilder()

    async def run(
        self,
        question: str,
        conversation_history: Sequence[dict[str, str]],
    ) -> dict:
        # LangChain orchestration should plug into this flow later without
        # changing the boundary above RAGService.
        query_embedding = await self._embedding_service.embed_text(question)
        retrieved_documents = await self._retriever.similarity_search(
            query_embedding=query_embedding,
            conversation_history=conversation_history,
        )

        context = RAGContext(
            question=question,
            conversation_history=conversation_history,
            retrieved_documents=retrieved_documents,
        )
        prompt = self._prompt_builder.build_prompt(context)
        answer = await self._llm_service.generate(prompt=prompt)

        response = RAGResponse(
            answer=answer,
            sources=[
                RAGSource(
                    title=document.metadata.get("title", document.id),
                    score=document.score,
                    metadata=document.metadata,
                )
                for document in retrieved_documents
            ],
        )
        return response.to_dict()
