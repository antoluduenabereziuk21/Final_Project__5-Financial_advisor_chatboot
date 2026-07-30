from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ChunkRecord:
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class SearchResult:
    content: str
    metadata: dict[str, Any]
    similarity: float
    id: int | None = None


@dataclass
class SearchParams:
    query_embedding: list[float]
    top_k: int = 5
    metadata_filter: dict[str, Any] | None = None
