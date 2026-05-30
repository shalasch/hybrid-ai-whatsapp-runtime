from app.config import settings
from app.contracts.decision_output import DecideResponse
from app.graph.state import DecisionGraphState


def validation_node(state: DecisionGraphState) -> DecisionGraphState:
    decision: DecideResponse = state["decision"]
    warnings = list(state.get("warnings", []))

    if decision.confidence < settings.human_escalation_threshold:
        warnings.append("confidence_below_human_escalation_threshold")
        decision.routing_action = "human_wait"
        decision.needs_human = True
        decision.message_body = "Vou encaminhar sua mensagem para uma pessoa da equipe te ajudar melhor."
    elif decision.confidence < settings.decision_confidence_threshold:
        warnings.append("confidence_below_decision_threshold")
        if decision.routing_action not in {"ask_name", "send_menu", "human_wait"}:
            decision.routing_action = "send_menu"
            decision.message_body = "Posso te ajudar com inglês offshore, inglês profissional, inglês geral, aula experimental ou suporte. Qual opção faz mais sentido para você?"

    decision.runtime_warnings = warnings
    return {**state, "decision": decision, "warnings": warnings}
