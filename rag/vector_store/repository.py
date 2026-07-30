from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg

from vector_store.client import VectorDbClient
from vector_store.models import ChunkRecord, SearchParams, SearchResult

_EMBEDDING_DIMS = 384


def _serialize_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


def _row_to_search_result(row: asyncpg.Record) -> SearchResult:
    return SearchResult(
        id=row["id"],
        content=row["content"],
        metadata=dict(row["metadata"]),
        similarity=float(row["similarity"]),
    )


def _row_to_chunk_record(row: asyncpg.Record) -> ChunkRecord:
    return ChunkRecord(
        id=row["id"],
        content=row["content"],
        embedding=list(row["embedding"]),
        metadata=dict(row["metadata"]),
        created_at=row["created_at"],
    )


class VectorRepository:
    def __init__(self, client: VectorDbClient):
        self._client = client

    async def init_schema(self, sql_path: str | Path = "init_db.sql") -> None:
        path = Path(__file__).parent / sql_path
        sql = path.read_text(encoding="utf-8")
        async with self._client.pool.acquire() as conn:
            await conn.execute(sql)

    async def insert_chunk(self, chunk: ChunkRecord) -> int:
        if len(chunk.embedding) != _EMBEDDING_DIMS:
            raise ValueError(
                f"Embedding dimension mismatch: expected {_EMBEDDING_DIMS}, got {len(chunk.embedding)}"
            )
        vec = _serialize_vector(chunk.embedding)
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO rag_documents (content, embedding, metadata)
                VALUES ($1, $2::vector, $3::jsonb)
                RETURNING id
                """,
                chunk.content,
                vec,
                chunk.metadata,
            )
            return row["id"]

    async def insert_chunks_batch(self, chunks: list[ChunkRecord]) -> list[int]:
        if not chunks:
            return []
        for c in chunks:
            if len(c.embedding) != _EMBEDDING_DIMS:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {_EMBEDDING_DIMS}, got {len(c.embedding)}"
                )
        async with self._client.pool.acquire() as conn:
            records = [
                (c.content, _serialize_vector(c.embedding), c.metadata)
                for c in chunks
            ]
            rows = await conn.fetch(
                """
                INSERT INTO rag_documents (content, embedding, metadata)
                SELECT * FROM UNNEST($1::text[], $2::vector[], $3::jsonb[])
                RETURNING id
                """,
                [r[0] for r in records],
                [r[1] for r in records],
                [r[2] for r in records],
            )
            return [r["id"] for r in rows]

    async def insert_chunks_batch_raw(self, chunks: list[dict]) -> list[int]:
        if not chunks:
            return []
        for c in chunks:
            emb = c["embedding"]
            if len(emb) != _EMBEDDING_DIMS:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {_EMBEDDING_DIMS}, got {len(emb)}"
                )
        async with self._client.pool.acquire() as conn:
            records = [
                (c["content"], _serialize_vector(c["embedding"]), c.get("metadata", {}))
                for c in chunks
            ]
            rows = await conn.fetch(
                """
                INSERT INTO rag_documents (content, embedding, metadata)
                SELECT * FROM UNNEST($1::text[], $2::vector[], $3::jsonb[])
                RETURNING id
                """,
                [r[0] for r in records],
                [r[1] for r in records],
                [r[2] for r in records],
            )
            return [r["id"] for r in rows]

    async def get_neighbors(
        self, chunk_id: int, window: int = 1
    ) -> list[SearchResult]:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, content, metadata, embedding FROM rag_documents WHERE id = $1",
                chunk_id,
            )
            if row is None:
                return []
            query_vec = _serialize_vector(list(row["embedding"]))
            rows = await conn.fetch(
                """
                (SELECT id, content, metadata,
                        1 - (embedding <=> $1::vector) AS similarity
                 FROM rag_documents
                 WHERE id < $2 ORDER BY id DESC LIMIT $3)
                UNION ALL
                (SELECT id, content, metadata,
                        1 - (embedding <=> $1::vector) AS similarity
                 FROM rag_documents
                 WHERE id > $2 ORDER BY id ASC LIMIT $3)
                ORDER BY similarity DESC
                """,
                query_vec,
                chunk_id,
                window,
            )
            return [_row_to_search_result(r) for r in rows]

    async def search_similar(self, params: SearchParams) -> list[SearchResult]:
        if len(params.query_embedding) != _EMBEDDING_DIMS:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {_EMBEDDING_DIMS}, "
                f"got {len(params.query_embedding)}"
            )
        vec = _serialize_vector(params.query_embedding)

        sql = """
            SELECT id, content, metadata, 1 - (embedding <=> $1::vector) AS similarity
            FROM rag_documents
        """
        conditions: list[str] = []
        values: list[Any] = [vec]

        if params.metadata_filter:
            conditions.append("metadata @> $" + str(len(values) + 1) + "::jsonb")
            values.append(params.metadata_filter)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY embedding <=> $1::vector LIMIT $" + str(len(values) + 1)
        values.append(params.top_k)

        async with self._client.pool.acquire() as conn:
            rows = await conn.fetch(sql, *values)
            return [_row_to_search_result(r) for r in rows]

    async def count(self) -> int:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchval("SELECT COUNT(*) FROM rag_documents")
            return row or 0

    async def get_by_id(self, chunk_id: int) -> ChunkRecord | None:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, content, embedding, metadata, created_at FROM rag_documents WHERE id = $1",
                chunk_id,
            )
            if row is None:
                return None
            return _row_to_chunk_record(row)

    async def delete_all(self) -> int:
        async with self._client.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM rag_documents")
            count = int(result.split()[-1])
            return count
