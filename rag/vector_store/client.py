from __future__ import annotations

import os
from typing import Self

import asyncpg


class VectorDbClient:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
    ):
        self._host = host or os.getenv("VECTOR_DB_HOST", "localhost")
        self._port = port or int(os.getenv("VECTOR_DB_PORT", "5432"))
        self._user = user or os.getenv("VECTOR_DB_USER", "ml_engineer")
        self._password = password or os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026")
        self._database = database or os.getenv("VECTOR_DB_NAME", "financial_rag_vectors")
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> Self:
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            min_size=self._min_pool_size,
            max_size=self._max_pool_size,
        )
        return self

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("VectorDbClient not connected – call .connect() first")
        return self._pool

    async def __aenter__(self) -> Self:
        return await self.connect()

    async def __aexit__(self, *args: object) -> None:
        await self.close()
