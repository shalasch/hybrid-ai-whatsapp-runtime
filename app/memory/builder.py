from app.contracts.runtime_context import RuntimeContext
from app.contracts.decision_output import MemoryUpdate


def build_memory_update(ctx: RuntimeContext, intent: str | None) -> MemoryUpdate:
    text = ctx.message.text or ""
    prior_summary = ctx.lead.lead_summary or ""
    compact = f"{prior_summary} Última mensagem: {text}".strip()[:700]
    interest_area = ctx.lead.interest_area
    lowered = text.lower()
    if any(k in lowered for k in ["offshore", "embarc", "plataforma", "navio"]):
        interest_area = "offshore"
    elif any(k in lowered for k in ["viagem", "travel", "aeroporto"]):
        interest_area = "general_english"
    return MemoryUpdate(
        lead_summary=compact or None,
        last_intent=intent,
        interest_area=interest_area,
        stage=ctx.conversation.etapa,
        last_messages_summary=text[:300] or ctx.lead.last_messages_summary,
    )
