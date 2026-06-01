"""
Tests for observability, trace IDs, audit logging, structured warnings,
node timing, and new state-aware validation gates.
"""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.contracts.decision_output import DecideResponse, RetrievalInfo
from app.contracts.runtime_warning import RuntimeWarning
from app.graph.nodes.validation_node import validation_node
from app.graph.state import DecisionGraphState
from app.contracts.runtime_context import (
    RuntimeContext, LeadContext, ConversationContext, MessageContext, RoutingContext,
)

client = TestClient(app)

_OFFSHORE_PAYLOAD = {
    "runtime_context": {
        "lead": {"id": "lead_obs", "nome": "Ana", "interesse": "offshore"},
        "conversation": {"id": "conv_obs", "session_id": "5521000000001", "etapa": "Menu", "status": "Ativa"},
        "message": {"text": "Quero treinar inglês para entrevista offshore", "type": "text", "idempotency_key": "obs_1"},
        "routing": {"previous_action": "send_menu"},
    }
}


# ── trace_id ──────────────────────────────────────────────────────────────────

def test_response_includes_trace_id():
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "trace_id" in data
    assert data["trace_id"] is not None
    assert data["trace_id"].startswith("trace_")


def test_trace_id_is_unique_per_request():
    r1 = client.post("/decide", json=_OFFSHORE_PAYLOAD).json()
    r2 = client.post("/decide", json=_OFFSHORE_PAYLOAD).json()
    assert r1["trace_id"] != r2["trace_id"]


def test_trace_id_format():
    data = client.post("/decide", json=_OFFSHORE_PAYLOAD).json()
    tid = data["trace_id"]
    assert tid.startswith("trace_")
    assert len(tid) == len("trace_") + 12  # "trace_" + 12 hex chars


# ── audit logger ──────────────────────────────────────────────────────────────

def test_audit_log_written_on_request(tmp_path, monkeypatch):
    import app.observability.audit_logger as al
    audit_path = tmp_path / "test_audit.jsonl"
    monkeypatch.setattr(al, "_get_path", lambda: audit_path)

    client.post("/decide", json=_OFFSHORE_PAYLOAD)

    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert "trace_id" in record
    assert "routing_action" in record
    assert "confidence" in record
    assert "timestamp" in record


def test_audit_record_fields(tmp_path, monkeypatch):
    import app.observability.audit_logger as al
    audit_path = tmp_path / "audit_fields.jsonl"
    monkeypatch.setattr(al, "_get_path", lambda: audit_path)

    client.post("/decide", json=_OFFSHORE_PAYLOAD)
    record = json.loads(audit_path.read_text().strip().splitlines()[-1])

    required = {"timestamp", "trace_id", "lead_id", "conversation_id",
                "routing_action", "confidence", "needs_human",
                "retrieval_used", "retrieval_sources", "runtime_warnings"}
    assert required.issubset(record.keys())


def test_audit_log_appends_multiple_requests(tmp_path, monkeypatch):
    import app.observability.audit_logger as al
    audit_path = tmp_path / "audit_multi.jsonl"
    monkeypatch.setattr(al, "_get_path", lambda: audit_path)

    client.post("/decide", json=_OFFSHORE_PAYLOAD)
    client.post("/decide", json=_OFFSHORE_PAYLOAD)

    lines = audit_path.read_text().strip().splitlines()
    assert len(lines) == 2
    ids = [json.loads(l)["trace_id"] for l in lines]
    assert ids[0] != ids[1]


def test_audit_log_survives_bad_path(monkeypatch):
    """Audit failures must not raise — runtime must continue."""
    import app.observability.audit_logger as al
    monkeypatch.setattr(al, "_get_path", lambda: pathlib.Path("/invalid/path/audit.jsonl"))

    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200  # runtime continues despite audit failure


# ── structured warnings ───────────────────────────────────────────────────────

def _make_state(
    routing_action="send_menu",
    confidence=0.85,
    needs_human=False,
    message_body="Olá.",
    intent=None,
    conv_status="Ativa",
    conv_etapa="Menu",
    lead_status=None,
    metadata=None,
) -> DecisionGraphState:
    ctx = RuntimeContext(
        lead=LeadContext(status=lead_status),
        conversation=ConversationContext(id="conv_sw", status=conv_status, etapa=conv_etapa),
        message=MessageContext(),
        routing=RoutingContext(),
        metadata=metadata or {},
    )
    decision = DecideResponse(
        routing_action=routing_action,
        confidence=confidence,
        needs_human=needs_human,
        message_body=message_body,
        reason="test",
    )
    return DecisionGraphState(runtime_context=ctx, intent=intent, decision=decision, warnings=[])


def test_structured_warnings_populated_on_low_confidence():
    state = _make_state(routing_action="send_quiz", confidence=0.55)
    result = validation_node(state)
    assert len(result["decision"].structured_warnings) > 0
    codes = [w.code for w in result["decision"].structured_warnings]
    assert "LOW_CONFIDENCE" in codes


def test_structured_warnings_have_required_fields():
    state = _make_state(routing_action="send_quiz", confidence=0.55)
    result = validation_node(state)
    for w in result["decision"].structured_warnings:
        assert isinstance(w, RuntimeWarning)
        assert w.code
        assert w.severity in {"info", "warning", "error"}
        assert w.source_node
        assert w.description


def test_structured_warnings_empty_on_clean_decision():
    state = _make_state(routing_action="send_menu", confidence=0.90, message_body="Olá.")
    result = validation_node(state)
    assert result["decision"].structured_warnings == []


def test_structured_warning_sensitive_intent():
    state = _make_state(intent="payment_inquiry", routing_action="send_menu", confidence=0.90)
    result = validation_node(state)
    codes = [w.code for w in result["decision"].structured_warnings]
    assert "SENSITIVE_INTENT" in codes


def test_structured_warning_duplicate_quiz():
    state = _make_state(routing_action="send_quiz", confidence=0.90, metadata={"quiz_sent": True})
    result = validation_node(state)
    codes = [w.code for w in result["decision"].structured_warnings]
    assert "DUPLICATE_QUIZ" in codes


def test_response_includes_structured_warnings_field():
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "structured_warnings" in data
    assert isinstance(data["structured_warnings"], list)


# ── new state-aware gates ─────────────────────────────────────────────────────

def test_awaiting_human_status_blocks_automation():
    state = _make_state(conv_status="Aguardando humano", routing_action="send_quiz", confidence=0.92)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert any("aguardando_humano" in w for w in result["decision"].runtime_warnings)


def test_lead_status_pausado_escalates():
    state = _make_state(lead_status="Pausado", routing_action="send_quiz", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert any("pausado" in w for w in result["decision"].runtime_warnings)


def test_etapa_captura_nome_forces_ask_name():
    state = _make_state(conv_etapa="Captura nome", routing_action="send_quiz", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "ask_name"
    assert "etapa_name_capture_forced_ask_name" in result["decision"].runtime_warnings


def test_etapa_saudacao_forces_ask_name():
    state = _make_state(conv_etapa="Saudação", routing_action="send_quiz", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "ask_name"


def test_etapa_captura_nome_allows_ask_name_through():
    state = _make_state(conv_etapa="Captura nome", routing_action="ask_name", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "ask_name"
    assert "etapa_name_capture_forced_ask_name" not in result["decision"].runtime_warnings


# ── retrieval info enrichment ─────────────────────────────────────────────────

def test_response_retrieval_info_has_top_scores():
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "retrieval" in data
    assert "top_scores" in data["retrieval"]
    assert isinstance(data["retrieval"]["top_scores"], list)


def test_response_retrieval_info_has_embedding_provider():
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    data = response.json()
    retrieval = data["retrieval"]
    if retrieval["used"]:
        assert retrieval["embedding_provider"] is not None


# ── node timing ───────────────────────────────────────────────────────────────

def test_validation_node_debug_includes_duration():
    state = _make_state(routing_action="send_menu", confidence=0.90, message_body="Olá.")
    result = validation_node(state)
    vdebug = result.get("debug", {}).get("validation_node", {})
    assert "duration_ms" in vdebug
    assert isinstance(vdebug["duration_ms"], float)
    assert vdebug["duration_ms"] >= 0


def test_classify_intent_debug_includes_duration():
    from app.graph.nodes.classify_intent import classify_intent
    ctx = RuntimeContext(
        lead=LeadContext(nome="Test"),
        conversation=ConversationContext(),
        message=MessageContext(text="offshore"),
        routing=RoutingContext(),
    )
    state = DecisionGraphState(runtime_context=ctx, warnings=[], debug={})
    result = classify_intent(state)
    assert result["debug"]["classify_intent"]["duration_ms"] >= 0


# ── schema hardening ──────────────────────────────────────────────────────────

def test_schema_hardening_injects_reason_if_missing():
    """If reason is empty, validation_node must inject a fallback."""
    ctx = RuntimeContext(
        lead=LeadContext(),
        conversation=ConversationContext(status="Ativa"),
        message=MessageContext(),
        routing=RoutingContext(),
    )
    decision = DecideResponse(
        routing_action="send_menu",
        confidence=0.85,
        reason="",          # intentionally empty
        message_body="Olá.",
    )
    state = DecisionGraphState(runtime_context=ctx, decision=decision, warnings=[])
    result = validation_node(state)
    assert result["decision"].reason  # must not be empty after hardening


def test_trace_id_propagated_to_decision(monkeypatch):
    """trace_id in graph state must appear on the DecideResponse."""
    ctx = RuntimeContext(
        lead=LeadContext(nome="Test"),
        conversation=ConversationContext(status="Ativa", etapa="Menu"),
        message=MessageContext(text="Quero inglês offshore"),
        routing=RoutingContext(),
    )
    decision = DecideResponse(
        routing_action="send_menu",
        confidence=0.85,
        reason="test",
        message_body="Olá.",
    )
    state = DecisionGraphState(
        runtime_context=ctx,
        decision=decision,
        warnings=[],
        trace_id="trace_abc123xyz",
    )
    result = validation_node(state)
    assert result["decision"].trace_id == "trace_abc123xyz"
