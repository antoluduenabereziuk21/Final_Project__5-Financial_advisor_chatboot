from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from embeddings.generate import embed_text
from llm.generator import configure as configure_llm, generate
from retrieval.retriever import retrieve
from vector_store.client import VectorDbClient
from vector_store.models import ChunkRecord
from vector_store.repository import VectorRepository

# Ensure ingestion/ is on sys.path so orchestrate.py's local imports work
_ingestion_dir = str(Path(__file__).parent / "ingestion")
if _ingestion_dir not in sys.path:
    sys.path.insert(0, _ingestion_dir)

app = FastAPI(title="RAG Service", version="0.1.0")


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    filters: dict | None = None
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    confidence_flag: str
    sources: list[dict]
    retrieval_meta: dict


class IngestRequest(BaseModel):
    pdf_path: str


@app.on_event("startup")
async def startup():
    client = VectorDbClient()
    await client.connect()
    app.state.db = client
    app.state.repo = VectorRepository(client)
    configure_llm("openai")


@app.on_event("shutdown")
async def shutdown():
    await app.state.db.close()


@app.get("/health")
async def health():
    count = await app.state.repo.count()
    return {"status": "ok", "documents_indexed": count}


@app.post("/ingest", summary="Process a PDF and index it in the vector store")
async def ingest(body: IngestRequest):
    path = Path(body.pdf_path)
    if not path.exists():
        raise HTTPException(404, f"PDF not found: {body.pdf_path}")

    from orchestrate import run_one

    result, _ = run_one(body.pdf_path)
    chunks = result["chunks_word_count"]

    chunk_records = []
    for idx, c in enumerate(chunks):
        meta = c.get("metadata", {})
        chunk_records.append(
            ChunkRecord(
                content=c["text"],
                embedding=embed_text(c["text"]),
                ticker=meta.get("ticker") or "",
                company=meta.get("company") or "",
                fiscal_year=meta.get("fiscal_year") or 0,
                form_type=meta.get("form_type"),
                accounting_standard=meta.get("accounting_standard"),
                canonical_section=meta.get("canonical_section"),
                source_file=body.pdf_path,
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                numeric_density=meta.get("numeric_density"),
                chunk_index=idx,
            )
        )
    ids = await app.state.repo.insert_chunks_batch(chunk_records)
    return {"message": "Ingestion complete", "chunks_indexed": len(ids)}


@app.post("/query", summary="Ask a question to the financial RAG pipeline")
async def query(body: QueryRequest):
    filters = body.filters or {}
    ticker = filters.get("ticker")
    company = filters.get("company")
    fiscal_year = filters.get("fiscal_year")

    sources, retrieval_meta = await retrieve(
        repo=app.state.repo,
        question=body.question,
        ticker=ticker,
        company=company,
        fiscal_year=fiscal_year,
        top_k=body.top_k,
    )

    answer, confidence_flag = await generate(body.question, sources)

    return QueryResponse(
        answer=answer,
        confidence_flag=confidence_flag,
        sources=sources,
        retrieval_meta=retrieval_meta,
    )


@app.post("/search", summary="Direct semantic search (legacy)")
async def search(body: QueryRequest):
    filters = body.filters or {}
    sources, retrieval_meta = await retrieve(
        repo=app.state.repo,
        question=body.question,
        ticker=filters.get("ticker"),
        company=filters.get("company"),
        fiscal_year=filters.get("fiscal_year"),
        top_k=body.top_k,
    )
    return {"sources": sources, "retrieval_meta": retrieval_meta}
