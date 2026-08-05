from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService
from app.rag.embeddings import MockEmbeddingService
from app.rag.llm import MockLLMService
from app.rag.prompt_builder import MockPromptBuilder
from app.rag.retriever import MockRetriever


def create_app() -> FastAPI:
    app = FastAPI(title="Financial Advisor Chatbot Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # This service graph is intentionally mock-friendly so the real LangChain,
    # OpenAI and vector-store integrations can be swapped in later without
    # touching endpoints or frontend contracts.
    rag_service = RAGService(
        retriever=MockRetriever(),
        embedding_service=MockEmbeddingService(),
        prompt_builder=MockPromptBuilder(),
        llm_service=MockLLMService(),
    )
    conversation_service = ConversationService()
    chat_service = ChatService(
        rag_service=rag_service,
        conversation_service=conversation_service,
    )

    app.state.chat_service = chat_service
    app.state.conversation_service = conversation_service
    app.state.rag_service = rag_service

    app.include_router(chat_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
