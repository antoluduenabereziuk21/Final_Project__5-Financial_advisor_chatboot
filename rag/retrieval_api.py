from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag.retrieval.retriever import retrieve
from rag.vector_store.supabase_repository import SupabaseVectorRepository


# Load local environment variables when a root .env exists.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")


class RetrievalFilters(BaseModel):
    ticker: list[str] | None = None
    company: list[str] | None = None
    fiscal_year: int | None = None


class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1)
    filters: RetrievalFilters | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalResponse(BaseModel):
    question: str
    sources: list[dict]
    retrieval_meta: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vector_repository = SupabaseVectorRepository()
    yield


app = FastAPI(
    title="Financial Advisor Vector Retrieval API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "vector_backend": "supabase_pgvector_rpc",
        "embedding_model": "all-MiniLM-L6-v2",
    }


@app.post(
    "/retrieve",
    response_model=RetrievalResponse,
    summary="Retrieve the most relevant financial document chunks",
)
async def retrieve_chunks(
    body: RetrievalRequest,
) -> RetrievalResponse:
    filters = body.filters or RetrievalFilters()

    try:
        sources, retrieval_meta = await retrieve(
            repo=app.state.vector_repository,
            question=body.question,
            ticker=filters.ticker,
            company=filters.company,
            fiscal_year=filters.fiscal_year,
            top_k=body.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Vector retrieval failed: {exc}",
        ) from exc

    return RetrievalResponse(
        question=body.question,
        sources=sources,
        retrieval_meta=retrieval_meta,
    )
