import time
from app.graph.state import DecisionGraphState
from app.contracts.decision_output import DecideResponse, ReasoningTrace, RetrievalInfo
from app.services.openai_client import get_client
from app.observability.logger import logger


def _make_retrieval_info(docs: list, embedding_provider: str) -> RetrievalInfo:
    return RetrievalInfo(
        used=bool(docs),
        sources=[d.source for d in docs],
        top_scores=[round(d.score, 4) for d in docs],
        embedding_provider=embedding_provider if docs else None,
    )


def _emit_decision_log(decision_mode: str, decision: DecideResponse, intent: str, doc_count: int, duration_ms: float) -> None:
    logger.info(
        "DECISION_NODE_COMPLETED",
        node_name="decision_node",
        decision_mode=decision_mode,
        routing_action=decision.routing_action,
        confidence=decision.confidence,
        needs_human=decision.needs_human,
        intent=intent,
        retrieved_doc_count=doc_count,
        duration_ms=duration_ms,
    )


def decision_node(state: DecisionGraphState) -> DecisionGraphState:
    _start = time.monotonic()
    ctx = state["runtime_context"]
    intent = state.get("intent", "unknown")
    docs = state.get("retrieved_docs", [])
    memory_update = state.get("memory_update")
    doc_count = len(docs)

    from app.config import settings
    embedding_provider = settings.rag_embedding_provider

    client = get_client()
    if client:
        try:
            ai = client.get_decision(ctx, intent, docs)
            duration_ms = round((time.monotonic() - _start) * 1000, 2)
            decision = DecideResponse(
                lead_id=ctx.lead.id,
                conversation_id=ctx.conversation.id,
                runtime_context=ctx,
                routing_action=ai.routing_action,
                message_type="text",
                message_body=ai.message_body,
                confidence=ai.confidence,
                needs_human=ai.needs_human,
                reason=ai.reason,
                reasoning=ReasoningTrace(
                    intent=intent,
                    matched_signals=ai.matched_signals,
                    risk_flags=ai.risk_flags,
                    decision_factors=["openai_structured_output", "runtime_context"],
                ),
                memory_update=memory_update,
                retrieval=_make_retrieval_info(docs, embedding_provider),
            )
            _emit_decision_log("openai_structured_output", decision, intent, doc_count, duration_ms)
            debug = {
                **state.get("debug", {}),
                "decision_node": {
                    "decision_mode": "openai_structured_output",
                    "routing_action": decision.routing_action,
                    "confidence": decision.confidence,
                    "intent": intent,
                    "retrieved_doc_count": doc_count,
                    "risk_flags": ai.risk_flags,
                    "duration_ms": duration_ms,
                },
            }
            return {**state, "decision": decision, "debug": debug}
        except Exception as exc:
            logger.warning("openai_decision_failed_using_fallback", error=str(exc))

    # --- deterministic fallback (no API key or OpenAI call failed) ---
    routing_action = "human_wait"
    message_body = "Vou encaminhar sua mensagem para uma pessoa da equipe te ajudar melhor."
    confidence = 0.55
    needs_human = False
    reason = "Fallback seguro aplicado."
    matched_signals: list[str] = []

    if intent == "missing_name":
        routing_action = "ask_name"
        message_body = "Oi! Para eu te ajudar melhor, pode me enviar seu nome completo?"
        confidence = 0.95
        reason = "Lead sem nome real cadastrado."
        matched_signals.append("lead.nome vazio")
    elif intent in {"offshore_interest", "route_payload_offshore_interview"}:
        routing_action = "send_quiz"
        message_body = "Perfeito. Posso te enviar um diagnóstico rápido de inglês para offshore e entrevistas?"
        confidence = 0.88
        reason = "Mensagem indica interesse em inglês offshore ou entrevista."
        matched_signals.append("offshore/interview signal")
    elif intent in {"trial_class_interest", "route_payload_trial_class"}:
        routing_action = "route_payload_trial_class"
        message_body = "Claro. A aula experimental gratuita ajuda a entender seu nível, objetivo e melhor formato de aula. Quer que eu encaminhe para agendamento?"
        confidence = 0.86
        reason = "Usuário demonstrou interesse em aula experimental."
        matched_signals.append("trial class signal")
    elif intent in {"student_support", "route_payload_student_support"}:
        routing_action = "route_payload_student_support"
        message_body = "Entendi. Vou direcionar sua solicitação para suporte de aluno para verificarem com cuidado."
        confidence = 0.78
        needs_human = True
        reason = "Assunto pode envolver aluno, pagamento, material ou suporte operacional."
        matched_signals.append("student/support signal")
    elif intent in {"human_support", "route_payload_human_support"}:
        routing_action = "human_wait"
        message_body = "Claro. Vou chamar uma pessoa da equipe para continuar o atendimento."
        confidence = 0.93
        needs_human = True
        reason = "Usuário pediu atendimento humano."
        matched_signals.append("human requested")
    elif intent == "general_question" and docs:
        routing_action = "answer_faq"
        message_body = docs[0].content
        confidence = 0.74
        reason = "Pergunta geral respondida com base na knowledge base."
        matched_signals.append("rag match")
    else:
        routing_action = "send_menu" if ctx.lead.nome else "ask_name"
        message_body = "Posso te ajudar com inglês offshore, inglês profissional, inglês geral, aula experimental ou suporte. Qual opção faz mais sentido para você?"
        confidence = 0.62
        reason = "Intenção insuficiente; menu seguro recomendado."
        matched_signals.append("low intent clarity")

    duration_ms = round((time.monotonic() - _start) * 1000, 2)
    decision = DecideResponse(
        lead_id=ctx.lead.id,
        conversation_id=ctx.conversation.id,
        runtime_context=ctx,
        routing_action=routing_action,  # type: ignore[arg-type]
        message_type="text",
        message_body=message_body,
        confidence=confidence,
        needs_human=needs_human,
        reason=reason,
        reasoning=ReasoningTrace(
            intent=intent,
            matched_signals=matched_signals,
            decision_factors=["deterministic_guardrails", "runtime_context"],
        ),
        memory_update=memory_update,  # type: ignore[arg-type]
        retrieval=_make_retrieval_info(docs, embedding_provider),
    )
    _emit_decision_log("deterministic_fallback", decision, intent, doc_count, duration_ms)
    debug = {
        **state.get("debug", {}),
        "decision_node": {
            "decision_mode": "deterministic_fallback",
            "routing_action": decision.routing_action,
            "confidence": decision.confidence,
            "intent": intent,
            "retrieved_doc_count": doc_count,
            "matched_signals": matched_signals,
            "duration_ms": duration_ms,
        },
    }
    return {**state, "decision": decision, "debug": debug}
