from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.conversation_repository import ConversationRepository
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService
from rag.retrieval.entity_resolver import EntityResolver, KnownEntity
from rag.vector_store.models import ChunkRecord


class DummyRootAdapter:
    """Minimal adapter returning real-looking retrieval data, standing in for
    the DB-backed RootRAGAdapterImpl. Used so the happy-path tests exercise
    ChatService's normalization logic against real metadata rather than a
    fabricated citation."""

    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict | None = None,
        top_k: int = 5,
    ) -> dict:
        return {
            "answer": "Apple's FY2025 10-K shows strong liquidity and operating cash flow.",
            "confidence_flag": "ok",
            "sources": [
                {
                    "chunk_id": "chunk-1",
                    "company": "Apple Inc.",
                    "ticker": "AAPL",
                    "fiscal_year": 2025,
                    "form_type": "10-K",
                    "accounting_standard": "US-GAAP",
                    "canonical_section": "Liquidity and Capital Resources",
                    "source_file": "aapl_2025_10k.pdf",
                    "page_start": 40,
                    "page_end": 42,
                    "relevance_score": 0.91,
                    "text_snippet": "Apple maintains a strong liquidity position...",
                }
            ],
            "retrieval_meta": {
                "filters_applied": filters or {},
                "chunks_considered": 1,
                "model": "all-MiniLM-L6-v2",
            },
        }


@pytest.fixture()
def client_with_adapter() -> TestClient:
    """Client backed by a working adapter -- exercises the normal retrieval path."""
    app.state.chat_service = ChatService(
        rag_service=RAGService(adapter=DummyRootAdapter()),
        conversation_service=ConversationService(),
    )
    return TestClient(app)


@pytest.fixture()
def client_no_adapter() -> TestClient:
    """Client with no RAG adapter wired -- exercises the degraded/unavailable
    path (DB and Supabase both unreachable at startup). Must not fabricate a
    source or a citation to paper over the outage."""
    app.state.chat_service = ChatService(
        rag_service=RAGService(),
        conversation_service=ConversationService(),
    )
    return TestClient(app)


class FilterCapturingAdapter:
    """Records the `filters` it's called with instead of doing real
    retrieval -- used to verify ChatService actually resolves and forwards
    entity-resolved filters (2.6) rather than always calling
    generate_answer() with none, which is what the endpoint did before."""

    def __init__(self) -> None:
        self.received_filters: dict | None | list = "not called"

    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict | None = None,
        top_k: int = 5,
    ) -> dict:
        self.received_filters = filters
        return {
            "answer": "respuesta",
            "confidence_flag": "ok",
            "sources": [],
            "retrieval_meta": {"filters_applied": filters or {}, "chunks_considered": 0, "model": "test"},
        }


@pytest.fixture()
def filter_capturing_setup() -> tuple[TestClient, FilterCapturingAdapter]:
    adapter = FilterCapturingAdapter()
    resolver = EntityResolver(
        [KnownEntity(company="antares-pharma-inc", ticker=None)]
    )
    app.state.chat_service = ChatService(
        rag_service=RAGService(adapter=adapter),
        conversation_service=ConversationService(),
        entity_resolver=resolver,
    )
    return TestClient(app), adapter


def test_resolvable_question_forwards_company_and_year_filters(
    filter_capturing_setup: tuple[TestClient, FilterCapturingAdapter],
) -> None:
    client, adapter = filter_capturing_setup
    response = client.post(
        "/api/chat",
        json={
            "message": "¿Qué pago recibió Antares Pharma de LEO Pharma en 2014?",
            "conversation_id": "filter-conv-1",
        },
    )
    assert response.status_code == 200
    assert adapter.received_filters == {
        "company": ["antares-pharma-inc"],
        "fiscal_year": 2014,
    }


def test_unresolvable_question_forwards_no_filters(
    filter_capturing_setup: tuple[TestClient, FilterCapturingAdapter],
) -> None:
    client, adapter = filter_capturing_setup
    response = client.post(
        "/api/chat",
        json={
            "message": "What is the capital of France?",
            "conversation_id": "filter-conv-2",
        },
    )
    assert response.status_code == 200
    assert adapter.received_filters is None


def test_chat_endpoint_returns_expected_contract(client_with_adapter: TestClient) -> None:
    response = client_with_adapter.post(
        "/api/chat",
        json={
            "message": "¿Cuál es la situación financiera de Apple?",
            "conversation_id": "123",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["conversation_id"] == "123"
    assert "answer" in payload
    assert "sources" in payload
    assert isinstance(payload["sources"], list)
    assert payload["sources"]
    # Title falls back to source_file (a real, non-fabricated identifier) --
    # DB-backed sources don't carry a "title" field, only source_file/company.
    assert payload["sources"][0]["title"] == "aapl_2025_10k.pdf"
    assert payload["sources"][0]["chunk_id"] == "chunk-1"


def test_chat_endpoint_without_adapter_returns_no_fabricated_source(
    client_no_adapter: TestClient,
) -> None:
    """Regression test: when no RAG adapter is wired up, the response must say
    the system is unavailable and must return zero sources -- it must not
    invent a source or citation. This used to return a fake
    "Apple Annual Report 2025" citation regardless of what was asked."""
    response = client_no_adapter.post(
        "/api/chat",
        json={
            "message": "¿Cuál es la situación financiera de Apple?",
            "conversation_id": "no-adapter-conv",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["sources"] == []
    assert "unavailable" in payload["answer"].lower()
    assert "Apple Annual Report 2025" not in payload["answer"]


def test_chat_feedback_endpoints_roundtrip(client_with_adapter: TestClient) -> None:
    chat_response = client_with_adapter.post(
        "/api/chat",
        json={
            "message": "Necesito una recomendacion para mi cartera",
            "conversation_id": "feedback-conv-1",
        },
    )
    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    message_id = chat_payload["message_id"]

    create_feedback_response = client_with_adapter.post(
        "/api/chat/feedback",
        json={
            "conversation_id": "feedback-conv-1",
            "message_id": message_id,
            "rating": "up",
            "reason": "Respuesta clara",
            "user_id": "user-123",
        },
    )

    assert create_feedback_response.status_code == 201
    created_payload = create_feedback_response.json()
    assert created_payload["conversation_id"] == "feedback-conv-1"
    assert created_payload["message_id"] == message_id
    assert created_payload["rating"] == "up"
    assert "feedback_id" in created_payload

    list_feedback_response = client_with_adapter.get(
        "/api/chat/feedback",
        params={"conversation_id": "feedback-conv-1"},
    )
    assert list_feedback_response.status_code == 200
    listed_payload = list_feedback_response.json()
    assert listed_payload["total"] >= 1
    assert listed_payload["items"]
    assert listed_payload["items"][-1]["message_id"] == message_id


def test_sources_endpoint_returns_source_detail_for_chat_source(
    client_with_adapter: TestClient,
) -> None:
    chat_response = client_with_adapter.post(
        "/api/chat",
        json={
            "message": "Muestrame la fuente",
            "conversation_id": "source-conv-1",
        },
    )
    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    first_source = chat_payload["sources"][0]
    chunk_id = first_source["chunk_id"]

    source_response = client_with_adapter.get(f"/api/sources/{chunk_id}")
    assert source_response.status_code == 200
    source_payload = source_response.json()
    assert source_payload["chunk_id"] == chunk_id
    assert source_payload["title"] == first_source["title"]


def test_sources_endpoint_returns_404_for_unknown_chunk(client_with_adapter: TestClient) -> None:
    source_response = client_with_adapter.get("/api/sources/does-not-exist")
    assert source_response.status_code == 404


# ----------------------------------------------------------------------------
# Persistence: replaces the in-memory conversation/feedback/source state that
# used to be lost on every restart (and never shared across replicas). These
# tests use fakes that implement the same interface as the real Postgres-
# backed ConversationRepository/VectorRepository, without a live database --
# state lives in the fake itself, not in ChatService/ConversationService, so
# building a *new* service instance against the *same* fake genuinely proves
# the data survived independently of the service that produced it (standing
# in for a backend process restart).
# ----------------------------------------------------------------------------


def test_normalize_conversation_id_accepts_uuid_and_rejects_arbitrary_strings() -> None:
    """Regression test for the flaw in the reverted persistence attempt
    (commit ad04386): a non-UUID conversation_id must never be silently
    remapped (previously via uuid5 hashing) to a deterministic-but-unrelated
    UUID -- that let an arbitrary client-chosen id collide with someone
    else's conversation. It must be treated as absent instead."""
    valid_id = str(uuid.uuid4())
    assert ConversationRepository._normalize_conversation_id(valid_id) == valid_id
    assert ConversationRepository._normalize_conversation_id("not-a-uuid") is None
    assert ConversationRepository._normalize_conversation_id(None) is None
    assert ConversationRepository._normalize_conversation_id("") is None


class FakeConversationRepository:
    """Stands in for the Postgres-backed ConversationRepository. State lives
    on this object, not on ConversationService/ChatService, so it can be
    reused across a fresh pair of service instances to simulate surviving a
    process restart."""

    def __init__(self) -> None:
        self._turns: dict[str, list[dict[str, Any]]] = {}
        self._feedback: dict[str, list[dict[str, Any]]] = {}
        self._next_message_id = 1

    async def ensure_conversation(
        self, conversation_id: str | None, user_id: int | None = None, title: str = ""
    ) -> str:
        normalized = ConversationRepository._normalize_conversation_id(conversation_id)
        resolved = normalized or str(uuid.uuid4())
        self._turns.setdefault(resolved, [])
        return resolved

    async def get_history(self, conversation_id: str) -> list[dict[str, str]]:
        return [
            {"role": t["role"], "content": t["content"]}
            for t in self._turns.get(conversation_id, [])
        ]

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        sources: list[dict[str, Any]] | None = None,
        confidence_flag: str | None = None,
        retrieval_meta: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> str:
        turns = self._turns.setdefault(conversation_id, [])
        turns.append({"role": "user", "content": user_message})
        message_id = str(self._next_message_id)
        self._next_message_id += 1
        turns.append({"role": "assistant", "content": assistant_message})
        return message_id

    async def save_feedback(
        self,
        message_id: str,
        conversation_id: str,
        rating: str,
        reason: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        feedback = {
            "feedback_id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "user_id": user_id,
            "created_at": "2026-09-01T00:00:00+00:00",
        }
        self._feedback.setdefault(conversation_id, []).append(feedback)
        return feedback

    async def list_feedback(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._feedback.get(conversation_id, []))


class HistoryCapturingAdapter:
    """Records the `conversation_history` it's called with, to verify it was
    actually loaded from the repository rather than starting empty every
    time (which is what an in-memory ConversationService would do once its
    process restarts)."""

    def __init__(self) -> None:
        self.received_history: list[dict[str, str]] | None = None

    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict | None = None,
        top_k: int = 5,
    ) -> dict:
        self.received_history = conversation_history
        return {
            "answer": f"respuesta a: {question}",
            "confidence_flag": "ok",
            "sources": [],
            "retrieval_meta": {"filters_applied": {}, "chunks_considered": 0, "model": "test"},
        }


def _chat_service_with_fake_repo(
    adapter: object, fake_repo: FakeConversationRepository
) -> ChatService:
    return ChatService(
        rag_service=RAGService(adapter=adapter),  # type: ignore[arg-type]
        conversation_service=ConversationService(fake_repo),  # type: ignore[arg-type]
        conversation_repository=fake_repo,  # type: ignore[arg-type]
    )


def test_conversation_history_survives_new_service_instance(
    client_with_adapter: TestClient,
) -> None:
    fake_repo = FakeConversationRepository()
    adapter = HistoryCapturingAdapter()

    app.state.chat_service = _chat_service_with_fake_repo(adapter, fake_repo)
    first_response = client_with_adapter.post(
        "/api/chat", json={"message": "primera pregunta"}
    )
    assert first_response.status_code == 200
    conversation_id = first_response.json()["conversation_id"]

    # Fresh ChatService/ConversationService instances sharing only the same
    # fake_repo -- simulates the backend process restarting between requests.
    app.state.chat_service = _chat_service_with_fake_repo(adapter, fake_repo)
    second_response = client_with_adapter.post(
        "/api/chat",
        json={"message": "segunda pregunta", "conversation_id": conversation_id},
    )
    assert second_response.status_code == 200
    assert adapter.received_history == [
        {"role": "user", "content": "primera pregunta"},
        {"role": "assistant", "content": "respuesta a: primera pregunta"},
    ]


def test_feedback_survives_new_service_instance(client_with_adapter: TestClient) -> None:
    fake_repo = FakeConversationRepository()
    adapter = HistoryCapturingAdapter()

    app.state.chat_service = _chat_service_with_fake_repo(adapter, fake_repo)
    chat_response = client_with_adapter.post(
        "/api/chat", json={"message": "necesito ayuda"}
    )
    conversation_id = chat_response.json()["conversation_id"]
    message_id = chat_response.json()["message_id"]

    feedback_response = client_with_adapter.post(
        "/api/chat/feedback",
        json={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "rating": "up",
        },
    )
    assert feedback_response.status_code == 201

    # New ChatService instance, same fake_repo -- simulates a restart.
    app.state.chat_service = _chat_service_with_fake_repo(adapter, fake_repo)
    list_response = client_with_adapter.get(
        "/api/chat/feedback", params={"conversation_id": conversation_id}
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["message_id"] == message_id


class FakeVectorRepoWithLookup:
    """Stands in for VectorRepository.get_by_id -- backed by real rag_chunks
    data instead of a process-local cache."""

    def __init__(self, records: dict[int, ChunkRecord]) -> None:
        self._records = records

    async def get_by_id(self, chunk_id: int) -> ChunkRecord | None:
        return self._records.get(chunk_id)


class IntChunkIdAdapter:
    """Sources with an int chunk_id, matching real retrieval (chunk_id is
    rag_chunks.id, see rag/retrieval/retriever.py) -- the previous in-memory
    `_source_index` only ever indexed string chunk_ids
    (`isinstance(chunk_id, str)`), so it silently never worked for real
    Postgres-backed traffic. This is what the DB-backed lookup fixes."""

    async def generate_answer(
        self,
        *,
        question: str,
        conversation_history: list[dict[str, str]],
        filters: dict | None = None,
        top_k: int = 5,
    ) -> dict:
        return {
            "answer": "Apple's FY2025 10-K shows strong liquidity.",
            "confidence_flag": "ok",
            "sources": [{"chunk_id": 42, "source_file": "aapl_2025_10k.pdf"}],
            "retrieval_meta": {"filters_applied": {}, "chunks_considered": 1, "model": "test"},
        }


def test_source_detail_backed_by_vector_repo_survives_new_service_instance(
    client_with_adapter: TestClient,
) -> None:
    vector_repo = FakeVectorRepoWithLookup(
        {
            42: ChunkRecord(
                id=42,
                content="Apple maintains a strong liquidity position...",
                embedding=[],
                ticker="AAPL",
                company="Apple Inc.",
                fiscal_year=2025,
                form_type="10-K",
                source_file="aapl_2025_10k.pdf",
                page_start=40,
                page_end=42,
            )
        }
    )

    app.state.chat_service = ChatService(
        rag_service=RAGService(adapter=IntChunkIdAdapter()),  # type: ignore[arg-type]
        conversation_service=ConversationService(),
        vector_repo=vector_repo,  # type: ignore[arg-type]
    )
    chat_response = client_with_adapter.post(
        "/api/chat", json={"message": "fuente", "conversation_id": "src-conv-1"}
    )
    assert chat_response.status_code == 200

    # New ChatService instance that never called handle_message -- its
    # in-memory _source_index is empty. The lookup must still work because
    # it goes through vector_repo.get_by_id, not the per-instance cache.
    app.state.chat_service = ChatService(
        rag_service=RAGService(adapter=IntChunkIdAdapter()),  # type: ignore[arg-type]
        conversation_service=ConversationService(),
        vector_repo=vector_repo,  # type: ignore[arg-type]
    )
    source_response = client_with_adapter.get("/api/sources/42")
    assert source_response.status_code == 200
    payload = source_response.json()
    assert payload["chunk_id"] == "42"
    assert payload["source_file"] == "aapl_2025_10k.pdf"
    assert payload["company"] == "Apple Inc."
