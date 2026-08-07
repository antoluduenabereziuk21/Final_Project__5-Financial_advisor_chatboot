from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg

from vector_store.client import VectorDbClient
from vector_store.models import ChunkRecord, SearchParams, SearchResult

_EMBEDDING_DIMS = 384


def _serialize_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


def _parse_embedding(value) -> list[float]:
    """asyncpg devuelve la columna vector como str (no hay codec registrado);
    convierte de vuelta a list[float] de forma robusta."""
    if isinstance(value, str):
        cleaned = value.strip("[]").replace(" ", "")
        return [float(v) for v in cleaned.split(",") if v != ""]
    return list(value)


def _validate_embedding(embedding: list[float]) -> None:
    if len(embedding) != _EMBEDDING_DIMS:
        raise ValueError(
            f"Embedding dimension mismatch: expected {_EMBEDDING_DIMS}, "
            f"got {len(embedding)}"
        )


def _row_to_search_result(row: asyncpg.Record) -> SearchResult:
    return SearchResult(
        id=row["id"],
        content=row["content"],
        similarity=float(row["similarity"]),
        ticker=row["ticker"],
        company=row["company"],
        fiscal_year=row["fiscal_year"],
        form_type=row["form_type"],
        accounting_standard=row["accounting_standard"],
        canonical_section=row["canonical_section"],
        source_file=row["source_file"],
        page_start=row["page_start"],
        page_end=row["page_end"],
    )


def _row_to_chunk_record(row: asyncpg.Record) -> ChunkRecord:
    return ChunkRecord(
        id=row["id"],
        content=row["content"],
        embedding=_parse_embedding(row["embedding"]),
        ticker=row["ticker"],
        company=row["company"],
        fiscal_year=row["fiscal_year"],
        form_type=row["form_type"],
        accounting_standard=row["accounting_standard"],
        canonical_section=row["canonical_section"],
        source_file=row["source_file"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        numeric_density=row["numeric_density"],
        document_id=row["document_id"],
        chunk_index=row["chunk_index"],
        created_at=row["created_at"],
    )


_SEARCH_COLUMNS = """
    id, content,
    1 - (embedding <=> $1::vector) AS similarity,
    ticker, company, fiscal_year, form_type, accounting_standard,
    canonical_section, source_file, page_start, page_end
"""


class VectorRepository:
    def __init__(self, client: VectorDbClient):
        self._client = client

    async def init_schema(self, sql_path: str | Path = "init_db.sql") -> None:
        path = Path(__file__).parent / sql_path
        sql = path.read_text(encoding="utf-8")
        async with self._client.pool.acquire() as conn:
            await conn.execute(sql)

    async def _ensure_document(self, conn: asyncpg.Connection, chunk: ChunkRecord) -> int:
        row = await conn.fetchrow(
            """
            INSERT INTO documents (source_file, ticker, company, fiscal_year,
                                   form_type, accounting_standard)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (source_file) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                company = EXCLUDED.company,
                fiscal_year = EXCLUDED.fiscal_year,
                form_type = EXCLUDED.form_type,
                accounting_standard = EXCLUDED.accounting_standard
            RETURNING id
            """,
            chunk.source_file,
            chunk.ticker,
            chunk.company,
            chunk.fiscal_year,
            chunk.form_type,
            chunk.accounting_standard,
        )
        return row["id"]

    @staticmethod
    def _chunk_insert_sql() -> str:
        return """
            INSERT INTO rag_chunks
                (document_id, chunk_index, content, embedding, ticker, company,
                 fiscal_year, form_type, accounting_standard, canonical_section,
                 source_file, page_start, page_end, numeric_density)
            VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id
        """

    async def insert_chunk(self, chunk: ChunkRecord) -> int:
        _validate_embedding(chunk.embedding)
        async with self._client.pool.acquire() as conn:
            document_id = await self._ensure_document(conn, chunk)
            row = await conn.fetchrow(
                self._chunk_insert_sql(),
                document_id,
                chunk.chunk_index,
                chunk.content,
                _serialize_vector(chunk.embedding),
                chunk.ticker,
                chunk.company,
                chunk.fiscal_year,
                chunk.form_type,
                chunk.accounting_standard,
                chunk.canonical_section,
                chunk.source_file,
                chunk.page_start,
                chunk.page_end,
                chunk.numeric_density,
            )
            return row["id"]

    async def insert_chunks_batch(self, chunks: list[ChunkRecord]) -> list[int]:
        if not chunks:
            return []
        ids: list[int] = []
        async with self._client.pool.acquire() as conn:
            async with conn.transaction():
                for chunk in chunks:
                    _validate_embedding(chunk.embedding)
                    document_id = await self._ensure_document(conn, chunk)
                    row = await conn.fetchrow(
                        self._chunk_insert_sql(),
                        document_id,
                        chunk.chunk_index,
                        chunk.content,
                        _serialize_vector(chunk.embedding),
                        chunk.ticker,
                        chunk.company,
                        chunk.fiscal_year,
                        chunk.form_type,
                        chunk.accounting_standard,
                        chunk.canonical_section,
                        chunk.source_file,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.numeric_density,
                    )
                    ids.append(row["id"])
        return ids

    async def get_neighbors(
        self, chunk_id: int, window: int = 1
    ) -> list[SearchResult]:
        """Vecinos contiguos por chunk_index dentro del mismo documento
        (contrato 3.4: rearmar tablas partidas sumando header + datos)."""
        async with self._client.pool.acquire() as conn:
            anchor = await conn.fetchrow(
                "SELECT document_id, chunk_index, embedding FROM rag_chunks WHERE id = $1",
                chunk_id,
            )
            if anchor is None:
                return []
            query_vec = _serialize_vector(_parse_embedding(anchor["embedding"]))
            rows = await conn.fetch(
                f"""
                SELECT {_SEARCH_COLUMNS}
                FROM rag_chunks
                WHERE document_id = $2
                  AND chunk_index BETWEEN $3 AND $4
                  AND id <> $5
                ORDER BY chunk_index ASC
                """,
                query_vec,
                anchor["document_id"],
                anchor["chunk_index"] - window,
                anchor["chunk_index"] + window,
                chunk_id,
            )
            return [_row_to_search_result(r) for r in rows]

    async def search_similar(self, params: SearchParams) -> list[SearchResult]:
        _validate_embedding(params.query_embedding)
        vec = _serialize_vector(params.query_embedding)

        sql = f"SELECT {_SEARCH_COLUMNS} FROM rag_chunks"
        conditions: list[str] = []
        values: list[Any] = [vec]

        if params.ticker:
            conditions.append(f"ticker = ANY(${len(values) + 1})")
            values.append(params.ticker)
        if params.company:
            conditions.append(f"company = ANY(${len(values) + 1})")
            values.append(params.company)
        if params.fiscal_year is not None:
            conditions.append(f"fiscal_year = ${len(values) + 1}")
            values.append(params.fiscal_year)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += f" ORDER BY embedding <=> $1::vector LIMIT ${len(values) + 1}"
        values.append(params.top_k)

        async with self._client.pool.acquire() as conn:
            rows = await conn.fetch(sql, *values)
            return [_row_to_search_result(r) for r in rows]

    async def count(self) -> int:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks")
            return row or 0

    async def get_by_id(self, chunk_id: int) -> ChunkRecord | None:
        async with self._client.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, document_id, chunk_index, content, embedding, ticker,
                       company, fiscal_year, form_type, accounting_standard,
                       canonical_section, source_file, page_start, page_end,
                       numeric_density, created_at
                FROM rag_chunks
                WHERE id = $1
                """,
                chunk_id,
            )
            if row is None:
                return None
            return _row_to_chunk_record(row)

    async def delete_all(self) -> int:
        """Limpia el corpus completo. DELETE sobre documents cascada a rag_chunks."""
        async with self._client.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM documents")
            count = int(result.split()[-1])
            return count
