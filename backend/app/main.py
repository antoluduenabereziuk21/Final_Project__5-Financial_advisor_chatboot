from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.routes import api_router
from app.core.settings import settings
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService


def create_app() -> FastAPI:
    app = FastAPI(
        title="Financial Advisor Chatbot API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.chat_service = ChatService(
        rag_service=RAGService(),
        conversation_service=ConversationService(),
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(chat_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()