from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBEDDING_DIMS = 384


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = _load_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    model = _load_model()
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
    return [v.tolist() for v in vectors]
