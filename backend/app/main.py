from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.routes import api_router
from app.core.settings import settings
from app.db import close_database, init_database, session_factory
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_database()
    try:
        yield
    finally:
        await close_database()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Financial Advisor Chatbot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    conversation_service = ConversationService(session_factory=session_factory)
    app.state.chat_service = ChatService(
        rag_service=RAGService(),
        conversation_service=conversation_service,
        session_factory=session_factory,
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(chat_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()