from __future__ import annotations

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.routes import api_router
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from rag.llm.generator import configure as configure_llm

    configure_llm("groq" if settings.groq_api_key else None)

    db_client = None
    repo = None

    # Supabase HTTPS/RPC integration - Emilio Chasipanta.
    # Purpose:
    # Query the shared Supabase pgvector dataset over HTTPS when a direct
    # PostgreSQL connection is unavailable. The original PostgreSQL path is
    # preserved below as a backward-compatible fallback.
    if settings.supabase_url and settings.supabase_key:
        try:
            from rag.vector_store.supabase_repository import SupabaseVectorRepository

            repo = SupabaseVectorRepository(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_key,
            )

            # Connectivity check using a lightweight estimated row count.
            await repo.count()

            app.state.repo = repo
            log.info("Connected to Supabase vector repository over HTTPS")
        except Exception:
            repo = None
            log.warning(
                "Could not connect to Supabase vector repository",
                exc_info=True,
            )

    # Original direct PostgreSQL/asyncpg implementation preserved as fallback.
    if repo is None:
        try:
            from rag.vector_store.client import VectorDbClient
            from rag.vector_store.repository import VectorRepository

            db_client = VectorDbClient(
                host=settings.vector_db_host,
                port=settings.vector_db_port,
                user=settings.vector_db_user,
                password=settings.vector_db_password,
                database=settings.vector_db_name,
            )
            await db_client.connect()
            app.state.db_client = db_client
            repo = VectorRepository(db_client)
            app.state.repo = repo
            log.info(
                "Connected to vector database at %s:%s",
                settings.vector_db_host,
                settings.vector_db_port,
            )
        except Exception:
            log.warning(
                "Could not connect to vector DB – running without RAG retrieval",
                exc_info=True,
            )

    if repo is not None:
        from app.rag.adapter import RootRAGAdapterImpl

        adapter = RootRAGAdapterImpl(repo=repo)
        app.state.chat_service = ChatService(
            rag_service=RAGService(adapter=adapter),
            conversation_service=ConversationService(),
        )
    else:
        app.state.chat_service = ChatService(
            rag_service=RAGService(),
            conversation_service=ConversationService(),
        )

    yield

    if db_client is not None:
        await db_client.close()


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

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(chat_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        count = 0
        repo = getattr(app.state, "repo", None)
        if repo is not None:
            count = await repo.count()
        return {"status": "ok", "chunks_indexed": count, "db_connected": repo is not None}

    return app


app = create_app()
