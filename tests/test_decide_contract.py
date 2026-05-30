from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_decide_missing_name_returns_ask_name():
    payload = {
        "runtime_context": {
            "lead": {"id": "lead_1", "nome": None},
            "conversation": {"id": "conv_1", "session_id": "5521999999999", "etapa": "Saudação", "status": "Ativa"},
            "message": {"text": "Oi", "type": "text", "idempotency_key": "msg_1"},
            "routing": {}
        }
    }
    response = client.post("/decide", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["routing_action"] == "ask_name"
    assert 0 <= data["confidence"] <= 1
