from app.rag.chain import RAGChain
from app.rag.embeddings import EmbeddingService, MockEmbeddingService
from app.rag.llm import LLMService, MockLLMService
from app.rag.prompt_builder import MockPromptBuilder, PromptBuilder
from app.rag.retriever import MockRetriever, Retriever


class RAGService:
    def __init__(
        self,
        retriever: Retriever | None = None,
        embedding_service: EmbeddingService | None = None,
        prompt_builder: PromptBuilder | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._retriever = retriever or MockRetriever()
        self._embedding_service = embedding_service or MockEmbeddingService()
        self._prompt_builder = prompt_builder or MockPromptBuilder()
        self._llm_service = llm_service or MockLLMService()
        self._chain = RAGChain(
            retriever=self._retriever,
            embedding_service=self._embedding_service,
            prompt_builder=self._prompt_builder,
            llm_service=self._llm_service,
        )

    async def generate_answer(
        self,
        question: str,
        conversation_history: list,
    ) -> dict:
        return await self._chain.run(question=question, conversation_history=conversation_history)
