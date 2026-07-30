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
