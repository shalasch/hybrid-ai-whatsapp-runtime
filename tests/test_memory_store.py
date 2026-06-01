from pathlib import Path
import pytest
import app.memory.store as store_module
from app.memory.store import get_memory, upsert_memory
from app.contracts.decision_output import MemoryUpdate


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect all store calls to a fresh temp database for each test."""
    monkeypatch.setattr(store_module, "_DB_PATH", tmp_path / "test_memory.sqlite")


# ── get_memory ────────────────────────────────────────────────────────────────

def test_get_memory_returns_none_for_unknown_lead():
    result = get_memory("lead_unknown", "conv_unknown")
    assert result is None


def test_get_memory_returns_none_for_missing_lead_id():
    assert get_memory(None, "conv_1") is None


def test_get_memory_returns_none_for_missing_conversation_id():
    assert get_memory("lead_1", None) is None


# ── upsert_memory ─────────────────────────────────────────────────────────────

def test_upsert_then_get_round_trip():
    memory = MemoryUpdate(
        lead_summary="Interesse em offshore confirmado.",
        last_intent="offshore_interest",
        goal="trabalhar em plataforma",
        interest_area="offshore",
        pain_points=["inglês técnico", "entrevistas"],
        stage="Qualificação",
        last_messages_summary="Quero treinar para entrevista offshore.",
    )
    upsert_memory("lead_rt", "conv_rt", memory)
    result = get_memory("lead_rt", "conv_rt")

    assert result is not None
    assert result.lead_summary == memory.lead_summary
    assert result.last_intent == memory.last_intent
    assert result.goal == memory.goal
    assert result.interest_area == memory.interest_area
    assert result.pain_points == memory.pain_points
    assert result.stage == memory.stage
    assert result.last_messages_summary == memory.last_messages_summary


def test_upsert_overwrites_existing_memory():
    first = MemoryUpdate(last_intent="general_question", interest_area="general_english")
    upsert_memory("lead_upd", "conv_upd", first)

    second = MemoryUpdate(last_intent="offshore_interest", interest_area="offshore")
    upsert_memory("lead_upd", "conv_upd", second)

    result = get_memory("lead_upd", "conv_upd")
    assert result is not None
    assert result.last_intent == "offshore_interest"
    assert result.interest_area == "offshore"


def test_upsert_is_silent_noop_for_missing_lead_id():
    upsert_memory(None, "conv_1", MemoryUpdate(last_intent="test"))
    assert get_memory(None, "conv_1") is None


def test_upsert_is_silent_noop_for_missing_conversation_id():
    upsert_memory("lead_1", None, MemoryUpdate(last_intent="test"))
    assert get_memory("lead_1", None) is None


def test_pain_points_stored_and_retrieved_as_list():
    memory = MemoryUpdate(pain_points=["pronuncia", "gramática", "fluência"])
    upsert_memory("lead_pp", "conv_pp", memory)
    result = get_memory("lead_pp", "conv_pp")
    assert result is not None
    assert result.pain_points == ["pronuncia", "gramática", "fluência"]


def test_empty_pain_points_round_trip():
    upsert_memory("lead_ep", "conv_ep", MemoryUpdate(pain_points=[]))
    result = get_memory("lead_ep", "conv_ep")
    assert result is not None
    assert result.pain_points == []


def test_null_fields_stored_and_retrieved():
    upsert_memory("lead_null", "conv_null", MemoryUpdate())
    result = get_memory("lead_null", "conv_null")
    assert result is not None
    assert result.lead_summary is None
    assert result.last_intent is None
    assert result.goal is None
    assert result.interest_area is None
    assert result.stage is None
    assert result.last_messages_summary is None


def test_multiple_leads_are_isolated():
    upsert_memory("lead_a", "conv_1", MemoryUpdate(interest_area="offshore"))
    upsert_memory("lead_b", "conv_1", MemoryUpdate(interest_area="general_english"))

    a = get_memory("lead_a", "conv_1")
    b = get_memory("lead_b", "conv_1")
    assert a is not None and a.interest_area == "offshore"
    assert b is not None and b.interest_area == "general_english"


def test_same_lead_different_conversations_are_isolated():
    upsert_memory("lead_x", "conv_morning", MemoryUpdate(stage="Saudação"))
    upsert_memory("lead_x", "conv_evening", MemoryUpdate(stage="Menu"))

    morning = get_memory("lead_x", "conv_morning")
    evening = get_memory("lead_x", "conv_evening")
    assert morning is not None and morning.stage == "Saudação"
    assert evening is not None and evening.stage == "Menu"


def test_database_file_is_created_automatically(tmp_path, monkeypatch):
    custom_path = tmp_path / "subdir" / "nested" / "runtime.sqlite"
    monkeypatch.setattr(store_module, "_DB_PATH", custom_path)

    upsert_memory("lead_fs", "conv_fs", MemoryUpdate(last_intent="test"))
    assert custom_path.exists()


# ── memory persistence through the API ───────────────────────────────────────

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_MEMORY_LEAD_PAYLOAD = {
    "runtime_context": {
        "lead": {"id": "lead_mem_api", "nome": "Ana Costa", "interesse": "offshore"},
        "conversation": {"id": "conv_mem_api", "session_id": "5521777777777", "etapa": "Menu", "status": "Ativa"},
        "message": {"text": "Quero treinar para entrevista offshore", "type": "text", "idempotency_key": "mem_api_1"},
        "routing": {"previous_action": "send_menu"},
    }
}


def test_decide_persists_memory_after_request():
    response = client.post("/decide", json=_MEMORY_LEAD_PAYLOAD)
    assert response.status_code == 200

    stored = get_memory("lead_mem_api", "conv_mem_api")
    assert stored is not None
    assert stored.last_intent is not None


def test_decide_memory_update_present_in_response():
    response = client.post("/decide", json=_MEMORY_LEAD_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "memory_update" in data
    assert isinstance(data["memory_update"], dict)


def test_decide_second_request_hydrates_from_stored_memory():
    # First request establishes memory
    client.post("/decide", json=_MEMORY_LEAD_PAYLOAD)
    stored_after_first = get_memory("lead_mem_api", "conv_mem_api")
    assert stored_after_first is not None

    # Second request should read and re-persist
    response = client.post("/decide", json=_MEMORY_LEAD_PAYLOAD)
    assert response.status_code == 200

    stored_after_second = get_memory("lead_mem_api", "conv_mem_api")
    assert stored_after_second is not None
