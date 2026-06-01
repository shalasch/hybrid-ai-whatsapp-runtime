import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.graph.nodes.validation_node import validation_node
from app.graph.state import DecisionGraphState
from app.contracts.decision_output import DecideResponse, MemoryUpdate
from app.contracts.runtime_context import (
    RuntimeContext, LeadContext, ConversationContext, MessageContext, RoutingContext,
)

client = TestClient(app)

_MISSING_NAME_PAYLOAD = {
    "runtime_context": {
        "lead": {"id": "lead_1", "nome": None},
        "conversation": {"id": "conv_1", "session_id": "5521999999999", "etapa": "Saudação", "status": "Ativa"},
        "message": {"text": "Oi", "type": "text", "idempotency_key": "msg_1"},
        "routing": {},
    }
}

_OFFSHORE_PAYLOAD = {
    "runtime_context": {
        "lead": {"id": "lead_42", "nome": "Carlos", "interesse": "offshore"},
        "conversation": {"id": "conv_42", "session_id": "5521888888888", "etapa": "Menu", "status": "Ativa"},
        "message": {"text": "Quero treinar inglês para entrevista offshore", "type": "text", "idempotency_key": "msg_2"},
        "routing": {"previous_action": "send_menu"},
    }
}


def test_decide_missing_name_returns_ask_name():
    response = client.post("/decide", json=_MISSING_NAME_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["routing_action"] == "ask_name"
    assert 0 <= data["confidence"] <= 1


def test_decide_response_includes_operational_identifiers():
    """n8n requires lead_id and conversation_id at the top level for downstream Airtable updates."""
    response = client.post("/decide", json=_MISSING_NAME_PAYLOAD)
    assert response.status_code == 200
    data = response.json()

    assert data["lead_id"] == "lead_1"
    assert data["conversation_id"] == "conv_1"


def test_decide_response_echoes_runtime_context():
    """n8n must be able to read the full runtime_context from the response without re-fetching."""
    response = client.post("/decide", json=_MISSING_NAME_PAYLOAD)
    assert response.status_code == 200
    data = response.json()

    assert "runtime_context" in data
    assert data["runtime_context"]["lead"]["id"] == "lead_1"
    assert data["runtime_context"]["conversation"]["id"] == "conv_1"
    assert data["runtime_context"]["conversation"]["session_id"] == "5521999999999"


def test_decide_offshore_identifiers_match_request():
    """Identifiers must reflect the specific lead in the request, not a default."""
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()

    assert data["lead_id"] == "lead_42"
    assert data["conversation_id"] == "conv_42"
    assert data["runtime_context"]["lead"]["id"] == "lead_42"
    assert data["runtime_context"]["conversation"]["id"] == "conv_42"


# ── validation_node unit tests ────────────────────────────────────────────────


def _make_state(
    routing_action: str = "send_menu",
    confidence: float = 0.85,
    needs_human: bool = False,
    message_type: str = "text",
    message_body: str | None = "Olá.",
    intent: str | None = None,
    conv_status: str = "Ativa",
    metadata: dict | None = None,
) -> DecisionGraphState:
    context = RuntimeContext(
        lead=LeadContext(),
        conversation=ConversationContext(id="conv_test", status=conv_status),
        message=MessageContext(),
        routing=RoutingContext(),
        metadata=metadata or {},
    )
    decision = DecideResponse(
        routing_action=routing_action,
        confidence=confidence,
        needs_human=needs_human,
        message_type=message_type,
        message_body=message_body,
        reason="test",
    )
    return DecisionGraphState(runtime_context=context, intent=intent, decision=decision, warnings=[])


# Gate 2: conversation status

def test_validation_pausada_blocks_automation():
    state = _make_state(conv_status="Pausada", routing_action="send_quiz", confidence=0.92)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert result["decision"].needs_human is True
    assert "conversation_pausada_automation_blocked" in result["decision"].runtime_warnings


def test_validation_finalizada_blocks_automation():
    state = _make_state(conv_status="Finalizada", routing_action="send_menu", confidence=0.92)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert "conversation_finalizada_automation_blocked" in result["decision"].runtime_warnings


# Gate 3: needs_human flag

def test_validation_needs_human_forces_human_wait():
    state = _make_state(needs_human=True, routing_action="send_quiz", confidence=0.85)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert "needs_human_flag_forced_human_wait" in result["decision"].runtime_warnings


def test_validation_needs_human_already_human_wait_no_duplicate_warning():
    state = _make_state(needs_human=True, routing_action="human_wait", confidence=0.85)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert "needs_human_flag_forced_human_wait" not in result["decision"].runtime_warnings


# Gate 4: sensitive intent

@pytest.mark.parametrize("intent", ["payment_inquiry", "billing_question", "support_request", "pagamento_pendente", "reembolso"])
def test_validation_sensitive_intent_escalates(intent: str):
    state = _make_state(intent=intent, routing_action="send_menu", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert "sensitive_intent_escalated_to_human_wait" in result["decision"].runtime_warnings


def test_validation_normal_intent_not_escalated():
    state = _make_state(intent="offshore_interest", routing_action="send_quiz", confidence=0.90)
    result = validation_node(state)
    assert result["decision"].routing_action == "send_quiz"
    assert "sensitive_intent_escalated_to_human_wait" not in result["decision"].runtime_warnings


# Gate 5: duplicate quiz

def test_validation_duplicate_quiz_prevented():
    state = _make_state(routing_action="send_quiz", confidence=0.90, metadata={"quiz_sent": True})
    result = validation_node(state)
    assert result["decision"].routing_action == "send_menu"
    assert "duplicate_quiz_prevented_routed_to_send_menu" in result["decision"].runtime_warnings


def test_validation_quiz_not_yet_sent_passes_through():
    state = _make_state(routing_action="send_quiz", confidence=0.90, metadata={"quiz_sent": False})
    result = validation_node(state)
    assert result["decision"].routing_action == "send_quiz"
    assert "duplicate_quiz_prevented_routed_to_send_menu" not in result["decision"].runtime_warnings


# Gate 6: confidence floors

def test_validation_confidence_below_floor_forces_human_wait():
    state = _make_state(routing_action="send_quiz", confidence=0.55)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert result["decision"].needs_human is True
    assert "confidence_below_floor_forced_human_wait" in result["decision"].runtime_warnings


def test_validation_low_confidence_high_risk_forces_human_wait():
    # 0.65 is between floor (0.60) and threshold (0.75); send_quiz is high-risk
    state = _make_state(routing_action="send_quiz", confidence=0.65)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"
    assert "low_confidence_high_risk_action_forced_human_wait" in result["decision"].runtime_warnings


@pytest.mark.parametrize("action", [
    "route_payload_offshore_interview",
    "route_payload_trial_class",
    "route_payload_student_support",
])
def test_validation_low_confidence_all_high_risk_actions_escalate(action: str):
    state = _make_state(routing_action=action, confidence=0.68)
    result = validation_node(state)
    assert result["decision"].routing_action == "human_wait"


def test_validation_low_confidence_safe_action_unchanged():
    # ask_name is a safe fallback — acceptable under reduced confidence
    state = _make_state(routing_action="ask_name", confidence=0.68)
    result = validation_node(state)
    assert result["decision"].routing_action == "ask_name"
    assert "low_confidence" not in " ".join(result["decision"].runtime_warnings)


def test_validation_high_confidence_high_risk_action_passes_through():
    state = _make_state(routing_action="send_quiz", confidence=0.88)
    result = validation_node(state)
    assert result["decision"].routing_action == "send_quiz"
    assert result["decision"].runtime_warnings == []


# Gate 7: message_body guard

def test_validation_message_body_missing_adds_fallback():
    state = _make_state(routing_action="send_menu", confidence=0.90, message_body=None)
    result = validation_node(state)
    assert result["decision"].message_body is not None
    assert len(result["decision"].message_body) > 0
    assert "message_body_missing_added_fallback" in result["decision"].runtime_warnings


def test_validation_message_body_present_not_overwritten():
    original = "Mensagem original do modelo."
    state = _make_state(routing_action="send_menu", confidence=0.90, message_body=original)
    result = validation_node(state)
    assert result["decision"].message_body == original


def test_validation_non_text_message_type_skips_body_guard():
    state = _make_state(routing_action="send_menu", confidence=0.90, message_type="interactive", message_body=None)
    result = validation_node(state)
    assert "message_body_missing_added_fallback" not in result["decision"].runtime_warnings


# Warnings accumulate correctly

def test_validation_clean_decision_produces_no_warnings():
    state = _make_state(routing_action="send_menu", confidence=0.90, message_body="Olá.")
    result = validation_node(state)
    assert result["decision"].runtime_warnings == []


# ── RAG retrieval integration ─────────────────────────────────────────────────


@pytest.fixture()
def ingested_kb_store():
    """
    Point the vector store at a test-only ChromaDB populated with ONNX embeddings.

    Using a separate path avoids mixing ONNX-embedded test data with production
    data/chroma/ which may use OpenAI embeddings. Restores original state after
    each test so surrounding tests are unaffected.
    """
    import app.rag.vector_store as vs
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    saved_collection = vs._collection
    saved_path = vs._chroma_path
    saved_make_ef = vs._make_embedding_function

    vs._collection = None
    vs._chroma_path = "data/chroma_test"
    vs._make_embedding_function = ONNXMiniLM_L6_V2  # bypass OpenAI — uses cached ONNX model

    vs.get_or_create_collection()  # triggers auto-ingest from knowledge_base/ via absolute path

    yield

    vs._collection = saved_collection
    vs._chroma_path = saved_path
    vs._make_embedding_function = saved_make_ef


def test_decide_offshore_retrieval_is_active(ingested_kb_store):
    """Offshore queries must use the knowledge base — retrieval.used must be True."""
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    retrieval = data.get("retrieval", {})
    assert retrieval.get("used") is True, (
        "retrieval.used is False — knowledge base may not be ingested. "
        "Run: python -m app.rag.ingest"
    )
    assert len(retrieval.get("sources", [])) > 0


def test_decide_retrieval_sources_are_strings(ingested_kb_store):
    response = client.post("/decide", json=_OFFSHORE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    for source in data.get("retrieval", {}).get("sources", []):
        assert isinstance(source, str)
        assert source  # no empty strings


# ── Memory deduplication ──────────────────────────────────────────────────────


def test_memory_build_does_not_duplicate_same_message():
    from app.memory.builder import build_memory_update
    from app.contracts.decision_output import MemoryUpdate

    ctx = RuntimeContext(
        lead=LeadContext(id="lead_dedup"),
        conversation=ConversationContext(id="conv_dedup", etapa="Menu"),
        message=MessageContext(text="Quero treinar para offshore"),
        routing=RoutingContext(),
    )
    first = build_memory_update(ctx, "offshore_interest")
    # Simulate second request: same message, stored first result
    second = build_memory_update(ctx, "offshore_interest", stored=first)

    assert second.lead_summary is not None
    assert second.lead_summary.count("Última mensagem:") == 1


def test_memory_build_overwrites_on_new_message():
    """lead_summary must reflect the CURRENT message only — not accumulate history."""
    from app.memory.builder import build_memory_update

    ctx_first = RuntimeContext(
        lead=LeadContext(id="lead_overwrite"),
        conversation=ConversationContext(id="conv_overwrite", etapa="Menu"),
        message=MessageContext(text="Primeira mensagem"),
        routing=RoutingContext(),
    )
    first = build_memory_update(ctx_first, "general_question")
    assert "Primeira mensagem" in first.lead_summary

    ctx_second = RuntimeContext(
        lead=LeadContext(id="lead_overwrite"),
        conversation=ConversationContext(id="conv_overwrite", etapa="Menu"),
        message=MessageContext(text="Segunda mensagem"),
        routing=RoutingContext(),
    )
    second = build_memory_update(ctx_second, "offshore_interest", stored=first)

    assert second.lead_summary is not None
    # New message replaces old one — no concatenation
    assert "Segunda mensagem" in second.lead_summary
    assert "Primeira mensagem" not in second.lead_summary
    assert second.lead_summary.count("Última mensagem:") == 1


def test_memory_build_empty_text_keeps_prior_summary():
    from app.memory.builder import build_memory_update

    stored = MemoryUpdate(lead_summary="Última mensagem: Mensagem anterior")
    ctx = RuntimeContext(
        lead=LeadContext(id="lead_empty"),
        conversation=ConversationContext(id="conv_empty"),
        message=MessageContext(text=None),
        routing=RoutingContext(),
    )
    result = build_memory_update(ctx, None, stored=stored)
    assert result.lead_summary == "Última mensagem: Mensagem anterior"


def test_memory_build_triple_repeat_no_duplication():
    """Three requests with the same message must still produce exactly one tag."""
    from app.memory.builder import build_memory_update

    ctx = RuntimeContext(
        lead=LeadContext(id="lead_triple"),
        conversation=ConversationContext(id="conv_triple", etapa="Menu"),
        message=MessageContext(text="Quero saber sobre offshore"),
        routing=RoutingContext(),
    )
    first = build_memory_update(ctx, "offshore_interest")
    second = build_memory_update(ctx, "offshore_interest", stored=first)
    third = build_memory_update(ctx, "offshore_interest", stored=second)

    assert third.lead_summary is not None
    assert third.lead_summary.count("Última mensagem:") == 1
    assert third.lead_summary.count("Quero saber sobre offshore") == 1


def test_memory_build_last_messages_summary_unchanged_on_repeat():
    """last_messages_summary must not change when the same message is re-processed."""
    from app.memory.builder import build_memory_update

    ctx = RuntimeContext(
        lead=LeadContext(id="lead_lms"),
        conversation=ConversationContext(id="conv_lms"),
        message=MessageContext(text="Mensagem repetida"),
        routing=RoutingContext(),
    )
    first = build_memory_update(ctx, "general_question")
    assert first.last_messages_summary == "Mensagem repetida"

    second = build_memory_update(ctx, "general_question", stored=first)
    # Value should stay the same, not be re-written
    assert second.last_messages_summary == "Mensagem repetida"


def test_memory_build_last_messages_summary_updated_on_new_message():
    """last_messages_summary must update when the message actually changes."""
    from app.memory.builder import build_memory_update

    ctx_a = RuntimeContext(
        lead=LeadContext(id="lead_lms2"),
        conversation=ConversationContext(id="conv_lms2"),
        message=MessageContext(text="Primeira"),
        routing=RoutingContext(),
    )
    stored = build_memory_update(ctx_a, "general_question")
    assert stored.last_messages_summary == "Primeira"

    ctx_b = RuntimeContext(
        lead=LeadContext(id="lead_lms2"),
        conversation=ConversationContext(id="conv_lms2"),
        message=MessageContext(text="Segunda"),
        routing=RoutingContext(),
    )
    result = build_memory_update(ctx_b, "general_question", stored=stored)
    assert result.last_messages_summary == "Segunda"


def test_memory_builder_node_no_duplication_on_repeated_message():
    """Full memory_builder node: repeated message must not duplicate lead_summary."""
    from app.graph.nodes.memory_builder import memory_builder
    from app.graph.state import DecisionGraphState
    import app.memory.store as store_module

    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        original = store_module._DB_PATH
        store_module._DB_PATH = pathlib.Path(tmp) / "test.sqlite"
        try:
            ctx = RuntimeContext(
                lead=LeadContext(id="lead_node_dedup", nome="Test"),
                conversation=ConversationContext(id="conv_node_dedup", status="Ativa"),
                message=MessageContext(text="Offshore entrevista", type="text"),
                routing=RoutingContext(),
            )
            state: DecisionGraphState = DecisionGraphState(
                runtime_context=ctx, intent="offshore_interest", warnings=[], debug={}
            )

            result1 = memory_builder(state)
            from app.memory.store import upsert_memory
            upsert_memory("lead_node_dedup", "conv_node_dedup", result1["memory_update"])

            result2 = memory_builder(state)
            summary = result2["memory_update"].lead_summary
            assert summary is not None
            assert summary.count("Última mensagem:") == 1
        finally:
            store_module._DB_PATH = original


# ── lead_summary overwrite correctness ───────────────────────────────────────


def test_lead_summary_at_most_one_tag_across_many_different_messages():
    """Even with many different messages, lead_summary must always have exactly one tag."""
    from app.memory.builder import build_memory_update

    messages = ["Quero offshore", "Tenho entrevista", "Preciso de ajuda", "Quando começa?"]
    ctx_base = RuntimeContext(
        lead=LeadContext(id="lead_many"),
        conversation=ConversationContext(id="conv_many"),
        routing=RoutingContext(),
    )
    stored = None
    for msg in messages:
        ctx = ctx_base.model_copy(update={"message": MessageContext(text=msg)})
        result = build_memory_update(ctx, "offshore_interest", stored=stored)
        assert result.lead_summary is not None
        assert result.lead_summary.count("Última mensagem:") == 1, (
            f"Got multiple tags after message '{msg}': {result.lead_summary!r}"
        )
        stored = result


def test_lead_summary_includes_interest_area_when_known():
    """When interest_area is detected, it should appear in lead_summary."""
    from app.memory.builder import build_memory_update

    ctx = RuntimeContext(
        lead=LeadContext(id="lead_ia"),
        conversation=ConversationContext(id="conv_ia"),
        message=MessageContext(text="Quero treinar para plataforma offshore"),
        routing=RoutingContext(),
    )
    result = build_memory_update(ctx, "offshore_interest")
    assert result.lead_summary is not None
    assert "offshore" in result.lead_summary
    assert "Última mensagem:" in result.lead_summary
    assert result.lead_summary.count("Última mensagem:") == 1


def test_lead_summary_without_interest_area_uses_plain_format():
    """Without a detected interest_area, format is 'Última mensagem: {text}'."""
    from app.memory.builder import build_memory_update

    ctx = RuntimeContext(
        lead=LeadContext(id="lead_plain"),
        conversation=ConversationContext(id="conv_plain"),
        message=MessageContext(text="Olá, tenho uma dúvida"),
        routing=RoutingContext(),
    )
    result = build_memory_update(ctx, "general_question")
    assert result.lead_summary == "Última mensagem: Olá, tenho uma dúvida"


def test_normalize_existing_stored_duplicate_summary():
    """Normalization must fix stored summaries that already have multiple tags."""
    from app.memory.builder import _normalize_summary

    broken = "Última mensagem: X Última mensagem: Y Última mensagem: Z"
    fixed = _normalize_summary(broken)
    assert fixed is not None
    assert fixed.count("Última mensagem:") == 1
    assert "Z" in fixed  # keeps the LAST fragment


def test_normalize_single_tag_unchanged():
    from app.memory.builder import _normalize_summary

    clean = "Lead interessado em offshore. Última mensagem: Preciso de ajuda"
    assert _normalize_summary(clean) == clean


def test_normalize_none_returns_none():
    from app.memory.builder import _normalize_summary

    assert _normalize_summary(None) is None
    assert _normalize_summary("") is None
