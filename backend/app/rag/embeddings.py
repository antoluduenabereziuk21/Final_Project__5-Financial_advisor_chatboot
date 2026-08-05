from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingService(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class MockEmbeddingService:
    async def embed_text(self, text: str) -> list[float]:
        return self._vectorize(text)

    async def embed_query(self, text: str) -> list[float]:
        return await self.embed_text(text)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def _vectorize(self, text: str) -> list[float]:
        # Replace this with OpenAIEmbeddings or another embedding provider.
        tokens = text.lower().split()
        base = float(len(tokens) or 1)
        return [base, float(sum(len(token) for token in tokens)), float(sum(ord(char) for char in text) % 1000)]
