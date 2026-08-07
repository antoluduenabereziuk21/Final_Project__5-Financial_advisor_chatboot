from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


# ----------------------------------------------------------------------------
# RAG / pgvector
# ----------------------------------------------------------------------------
@dataclass
class ChunkRecord:
    """Un chunk indexado en rag_chunks. Campos tipados segun el contrato
    (docs/rag_pipeline_contrato.docx, seccion 2.1)."""

    content: str
    embedding: list[float]
    ticker: str
    company: str
    fiscal_year: int
    form_type: str | None = None
    accounting_standard: str | None = None
    canonical_section: str | None = None
    source_file: str = ""
    page_start: int | None = None
    page_end: int | None = None
    numeric_density: float | None = None
    document_id: int | None = None
    chunk_index: int | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class SearchResult:
    id: int
    content: str
    similarity: float
    ticker: str
    company: str
    fiscal_year: int
    form_type: str | None = None
    accounting_standard: str | None = None
    canonical_section: str | None = None
    source_file: str = ""
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class SearchParams:
    query_embedding: list[float]
    top_k: int = 5
    ticker: list[str] | None = None
    company: list[str] | None = None
    fiscal_year: int | None = None


# ----------------------------------------------------------------------------
# Aplicacion: usuarios y chat
# ----------------------------------------------------------------------------
@dataclass
class UserRecord:
    email: str
    username: str
    password_hash: str
    is_active: bool = True
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ConversationRecord:
    user_id: int | None = None
    title: str = "Nueva conversacion"
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ChatMessageRecord:
    conversation_id: str
    role: str
    content: str
    sources: list[dict[str, Any]] | None = None
    confidence_flag: str | None = None
    retrieval_meta: dict[str, Any] | None = None
    id: int | None = None
    created_at: datetime | None = None
