from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService
from rag.retrieval.entity_resolver import EntityResolver, KnownEntity


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
