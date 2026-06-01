import time
from app.config import settings
from app.contracts.decision_output import DecideResponse
from app.contracts.routing_actions import ALLOWED_ROUTING_ACTIONS
from app.contracts.runtime_warning import RuntimeWarning, WarningCode, WarningSeverity
from app.graph.state import DecisionGraphState
from app.observability.logger import logger

# Intents that carry financial or support risk — prefer human review
_SENSITIVE_INTENT_TERMS = {
    "payment", "billing", "refund", "cancellation", "complaint",
    "pagamento", "suporte", "cancelamento", "reembolso", "support",
}

# Conversation statuses that must not receive automated routing
_BLOCKED_CONV_STATUSES = {"Pausada", "Finalizada", "Aguardando humano"}

# Lead statuses that require human escalation
_BLOCKED_LEAD_STATUSES = {"Pausado"}

# Conversation etapas where advanced routing should not fire
_NAME_CAPTURE_ETAPAS = {"Captura nome", "Saudação"}

# High-risk actions: downstream side-effects, require high confidence
_HIGH_RISK_ACTIONS = {
    "send_quiz",
    "route_payload_offshore_interview",
    "route_payload_professional_english",
    "route_payload_general_english",
    "route_payload_trial_class",
    "route_payload_student_support",
    "route_payload_human_support",
}

# Safe fallback actions: acceptable under reduced confidence
_SAFE_FALLBACK_ACTIONS = {"ask_name", "capture_name", "send_menu", "human_wait", "ask_goal", "answer_faq"}

_MSG_HUMAN_WAIT = "Vou encaminhar sua mensagem para uma pessoa da equipe te ajudar melhor."
_MSG_SEND_MENU = (
    "Posso te ajudar com inglês offshore, inglês profissional, inglês geral, "
    "aula experimental ou suporte. Qual opção faz mais sentido para você?"
)

# Maps existing string warning keys → structured warning taxonomy
_STRING_TO_STRUCTURED: dict[str, tuple[WarningCode, WarningSeverity, str]] = {
    "invalid_routing_action_forced_human_wait": (
        "INVALID_ROUTING_ACTION", "error", "Routing action not in allowed enum — escalated to human_wait"),
    "needs_human_flag_forced_human_wait": (
        "HUMAN_ESCALATION", "info", "AI decision requested human escalation"),
    "sensitive_intent_escalated_to_human_wait": (
        "SENSITIVE_INTENT", "error", "Sensitive intent detected — escalated to human_wait"),
    "duplicate_quiz_prevented_routed_to_send_menu": (
        "DUPLICATE_QUIZ", "info", "Quiz already sent — duplicate prevented, routed to send_menu"),
    "confidence_below_floor_forced_human_wait": (
        "LOW_CONFIDENCE", "error", "Confidence below floor threshold — escalated to human_wait"),
    "low_confidence_high_risk_action_forced_human_wait": (
        "LOW_CONFIDENCE", "warning", "Low confidence with high-risk action — escalated to human_wait"),
    "low_confidence_routed_to_send_menu": (
        "LOW_CONFIDENCE", "warning", "Low confidence — routed to safe fallback send_menu"),
    "message_body_missing_added_fallback": (
        "EMPTY_MESSAGE_BODY", "warning", "message_body was empty for text response — fallback injected"),
    "schema_fallback_reason_injected": (
        "FALLBACK_RESPONSE", "warning", "reason field was empty — default injected"),
}


def _str_prefix_to_structured(key: str) -> tuple[WarningCode, WarningSeverity, str] | None:
    """Match prefixed string keys (e.g. conversation_pausada_automation_blocked)."""
    if key.startswith("conversation_") and key.endswith("_automation_blocked"):
        status = key[len("conversation_"):-len("_automation_blocked")]
        return ("STATE_BLOCKED", "error", f"Conversation status '{status}' — automation blocked")
    if key.startswith("lead_status_") and key.endswith("_automation_blocked"):
        status = key[len("lead_status_"):-len("_automation_blocked")]
        return ("STATE_BLOCKED", "warning", f"Lead status '{status}' — escalated to human_wait")
    if key == "etapa_name_capture_forced_ask_name":
        return ("VALIDATION_OVERRIDE", "info", "Conversation in name-capture stage — forced ask_name")
    if key.startswith("vector_retrieval_failed"):
        return ("RETRIEVAL_FAILED", "warning", "Vector retrieval failed — keyword fallback used")
    return None


def _force_human_wait(decision: DecideResponse, warnings: list[str], key: str) -> None:
    warnings.append(key)
    decision.routing_action = "human_wait"
    decision.needs_human = True
    if not decision.message_body:
        decision.message_body = _MSG_HUMAN_WAIT


def _force_send_menu(decision: DecideResponse, warnings: list[str], key: str) -> None:
    warnings.append(key)
    decision.routing_action = "send_menu"
    if not decision.message_body:
        decision.message_body = _MSG_SEND_MENU


def _intent_is_sensitive(intent: str | None) -> bool:
    if not intent:
        return False
    lower = intent.lower()
    return any(term in lower for term in _SENSITIVE_INTENT_TERMS)


def validation_node(state: DecisionGraphState) -> DecisionGraphState:
    _start = time.monotonic()
    decision: DecideResponse = state["decision"]
    context = state.get("runtime_context")
    intent: str | None = state.get("intent")
    warnings: list[str] = list(state.get("warnings", []))

    # Snapshot pre-validation state
    routing_action_before = decision.routing_action
    confidence_before = decision.confidence
    warnings_before = set(warnings)

    # ── Gate 1: routing_action enum contract ─────────────────────────────────
    if decision.routing_action not in ALLOWED_ROUTING_ACTIONS:
        _force_human_wait(decision, warnings, "invalid_routing_action_forced_human_wait")

    # ── Gates 2–6: state-aware + business rules (priority order, first match) ─
    conv_status = context.conversation.status if context else None
    conv_etapa = context.conversation.etapa if context else None
    lead_status = context.lead.status if context else None
    quiz_sent = bool(context.metadata.get("quiz_sent")) if context else False

    if conv_status in _BLOCKED_CONV_STATUSES:
        _force_human_wait(decision, warnings, f"conversation_{conv_status.lower().replace(' ', '_')}_automation_blocked")

    elif lead_status in _BLOCKED_LEAD_STATUSES:
        _force_human_wait(decision, warnings, f"lead_status_{lead_status.lower()}_automation_blocked")

    elif conv_etapa in _NAME_CAPTURE_ETAPAS and decision.routing_action not in {"ask_name", "capture_name"}:
        warnings.append("etapa_name_capture_forced_ask_name")
        decision.routing_action = "ask_name"
        if not decision.message_body:
            decision.message_body = "Oi! Para eu te ajudar melhor, pode me enviar seu nome completo?"

    elif decision.needs_human and decision.routing_action != "human_wait":
        _force_human_wait(decision, warnings, "needs_human_flag_forced_human_wait")

    elif _intent_is_sensitive(intent):
        _force_human_wait(decision, warnings, "sensitive_intent_escalated_to_human_wait")

    elif decision.routing_action == "send_quiz" and quiz_sent:
        _force_send_menu(decision, warnings, "duplicate_quiz_prevented_routed_to_send_menu")

    # ── Gate 7: confidence floors ─────────────────────────────────────────────
    if decision.confidence < settings.human_escalation_threshold:
        if decision.routing_action != "human_wait":
            _force_human_wait(decision, warnings, "confidence_below_floor_forced_human_wait")
    elif decision.confidence < settings.decision_confidence_threshold:
        if decision.routing_action not in _SAFE_FALLBACK_ACTIONS:
            if decision.routing_action in _HIGH_RISK_ACTIONS:
                _force_human_wait(decision, warnings, "low_confidence_high_risk_action_forced_human_wait")
            else:
                _force_send_menu(decision, warnings, "low_confidence_routed_to_send_menu")

    # ── Gate 8: message_body required for text responses ─────────────────────
    if decision.message_type == "text" and not decision.message_body:
        warnings.append("message_body_missing_added_fallback")
        decision.message_body = _MSG_SEND_MENU

    # ── Schema hardening: guarantee required fields are populated ─────────────
    if not decision.reason:
        decision.reason = "Routing decision processed."
        warnings.append("schema_fallback_reason_injected")

    # ── Propagate trace_id from state ─────────────────────────────────────────
    decision.trace_id = state.get("trace_id")

    decision.runtime_warnings = warnings

    # ── Build structured warnings from this run's overrides ──────────────────
    validation_overrides = [w for w in warnings if w not in warnings_before]
    structured: list[RuntimeWarning] = []
    for key in validation_overrides:
        entry = _STRING_TO_STRUCTURED.get(key) or _str_prefix_to_structured(key)
        if entry:
            code, severity, description = entry
            structured.append(RuntimeWarning(code=code, severity=severity, source_node="validation_node", description=description))

    decision.structured_warnings = structured

    routing_action_after = decision.routing_action
    duration_ms = round((time.monotonic() - _start) * 1000, 2)

    logger.info(
        "VALIDATION_NODE_COMPLETED",
        node_name="validation_node",
        trace_id=decision.trace_id,
        confidence_before_validation=confidence_before,
        confidence_after_validation=decision.confidence,
        routing_action_before_validation=routing_action_before,
        routing_action_after_validation=routing_action_after,
        validation_overrides=validation_overrides,
        structured_warning_count=len(structured),
        needs_human_after=decision.needs_human,
        overrides_applied=len(validation_overrides) > 0,
        duration_ms=duration_ms,
    )

    debug = {
        **state.get("debug", {}),
        "validation_node": {
            "confidence_before_validation": confidence_before,
            "confidence_after_validation": decision.confidence,
            "routing_action_before_validation": routing_action_before,
            "routing_action_after_validation": routing_action_after,
            "validation_overrides": validation_overrides,
            "structured_warning_count": len(structured),
            "needs_human_after": decision.needs_human,
            "duration_ms": duration_ms,
        },
    }

    return {**state, "decision": decision, "warnings": warnings, "debug": debug}
