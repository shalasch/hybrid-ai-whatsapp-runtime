from app.graph.state import DecisionGraphState


def classify_intent(state: DecisionGraphState) -> DecisionGraphState:
    ctx = state["runtime_context"]
    text = (ctx.message.text or "").lower().strip()
    payload = (ctx.message.payload or "").lower().strip()

    if payload:
        intent = payload
    elif not ctx.lead.nome:
        intent = "missing_name"
    elif any(k in text for k in ["quiz", "teste", "offshore", "embarc", "plataforma"]):
        intent = "offshore_interest"
    elif any(k in text for k in ["experimental", "aula grátis", "aula gratuita", "agendar"]):
        intent = "trial_class_interest"
    elif any(k in text for k in ["pagamento", "boleto", "pix", "aluno", "material"]):
        intent = "student_support"
    elif any(k in text for k in ["humano", "atendente", "professora", "falar com alguém"]):
        intent = "human_support"
    elif text:
        intent = "general_question"
    else:
        intent = "unknown"

    return {**state, "intent": intent, "debug": {**state.get("debug", {}), "intent": intent}}
