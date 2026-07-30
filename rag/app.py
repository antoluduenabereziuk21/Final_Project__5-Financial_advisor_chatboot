from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vector_store.client import VectorDbClient
from vector_store.models import SearchParams
from vector_store.repository import VectorRepository

app = FastAPI(title="RAG Service", version="0.1.0")


@app.on_event("startup")
async def startup():
    client = VectorDbClient()
    await client.connect()
    app.state.db = client
    app.state.repo = VectorRepository(client)


@app.on_event("shutdown")
async def shutdown():
    await app.state.db.close()


class SearchRequest(BaseModel):
    query_embedding: list[float]
    top_k: int = 5
    metadata_filter: dict | None = None


class IngestRequest(BaseModel):
    pdf_path: str


class SearchResponse(BaseModel):
    results: list[dict]


@app.get("/health")
async def health():
    count = await app.state.repo.count()
    return {"status": "ok", "documents_indexed": count}


@app.post("/ingest", summary="Process a PDF and index it in the vector store")
async def ingest(body: IngestRequest):
    path = Path(body.pdf_path)
    if not path.exists():
        raise HTTPException(404, f"PDF not found: {body.pdf_path}")

    from ingestion.orchestrate import run_one

    result, _ = run_one(body.pdf_path)
    return {"message": "Ingestion complete", "chunks": result["n_chunks_word_count"]}


@app.post("/search", summary="Semantic search over indexed chunks")
async def search(body: SearchRequest):
    params = SearchParams(
        query_embedding=body.query_embedding,
        top_k=body.top_k,
        metadata_filter=body.metadata_filter,
    )
    results = await app.state.repo.search_similar(params)
    return SearchResponse(
        results=[
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "similarity": r.similarity,
            }
            for r in results
        ]
    )
