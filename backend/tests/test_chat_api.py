from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_endpoint_returns_expected_contract() -> None:
    response = client.post(
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
    assert payload["sources"][0]["title"] == "Apple Annual Report 2025"


def test_chat_feedback_endpoints_roundtrip() -> None:
    chat_response = client.post(
        "/api/chat",
        json={
            "message": "Necesito una recomendacion para mi cartera",
            "conversation_id": "feedback-conv-1",
        },
    )
    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    message_id = chat_payload["message_id"]

    create_feedback_response = client.post(
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

    list_feedback_response = client.get(
        "/api/chat/feedback",
        params={"conversation_id": "feedback-conv-1"},
    )
    assert list_feedback_response.status_code == 200
    listed_payload = list_feedback_response.json()
    assert listed_payload["total"] >= 1
    assert listed_payload["items"]
    assert listed_payload["items"][-1]["message_id"] == message_id


def test_sources_endpoint_returns_source_detail_for_chat_source() -> None:
    chat_response = client.post(
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

    source_response = client.get(f"/api/sources/{chunk_id}")
    assert source_response.status_code == 200
    source_payload = source_response.json()
    assert source_payload["chunk_id"] == chunk_id
    assert source_payload["title"] == first_source["title"]


def test_sources_endpoint_returns_404_for_unknown_chunk() -> None:
    source_response = client.get("/api/sources/does-not-exist")
    assert source_response.status_code == 404
