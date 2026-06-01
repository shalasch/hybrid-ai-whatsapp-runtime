from app.contracts.runtime_context import RuntimeContext
from app.contracts.decision_output import MemoryUpdate

_TAG = "Última mensagem:"


def _normalize_summary(summary: str | None) -> str | None:
    """If a stored summary has multiple 'Última mensagem:' fragments (from old
    concatenation), keep only the last fragment. Returns None if empty."""
    if not summary:
        return None
    count = summary.count(_TAG)
    if count <= 1:
        return summary.strip() or None
    idx = summary.rfind(_TAG)
    return summary[idx:].strip()[:700] or None


def _fresh_summary(text: str, interest_area: str | None) -> str | None:
    """Build a clean, single-fragment summary. Always overwrites — never appends."""
    if not text:
        return None
    prefix = f"Lead interessado em {interest_area}. " if interest_area else ""
    return f"{prefix}{_TAG} {text}".strip()[:700]


def build_memory_update(
    ctx: RuntimeContext,
    intent: str | None,
    stored: MemoryUpdate | None = None,
) -> MemoryUpdate:
    text = ctx.message.text or ""

    # Determine interest_area (signal detection unchanged)
    interest_area = ctx.lead.interest_area or (stored.interest_area if stored else None)
    lowered = text.lower()
    if any(k in lowered for k in ["offshore", "embarc", "plataforma", "navio"]):
        interest_area = "offshore"
    elif any(k in lowered for k in ["viagem", "travel", "aeroporto"]):
        interest_area = "general_english"

    # Always build a FRESH summary — never concatenate to prior_summary.
    # If there is a current message, overwrite completely.
    # If there is no message, keep the stored summary but normalize out any
    # accumulated "Última mensagem:" fragments from previous broken runs.
    if text:
        compact: str | None = _fresh_summary(text, interest_area)
    else:
        raw = (stored.lead_summary if stored else None) or ctx.lead.lead_summary or None
        compact = _normalize_summary(raw)

    # Only update last_messages_summary when the text actually changed
    prior_last = (stored.last_messages_summary if stored else None) or ctx.lead.last_messages_summary or ""
    if text and text[:300] != prior_last:
        last_messages_summary: str | None = text[:300]
    else:
        last_messages_summary = prior_last or None

    return MemoryUpdate(
        lead_summary=compact or None,
        last_intent=intent or (stored.last_intent if stored else None),
        goal=ctx.lead.goal or (stored.goal if stored else None),
        interest_area=interest_area,
        stage=ctx.conversation.etapa or (stored.stage if stored else None),
        last_messages_summary=last_messages_summary,
    )


def enrich_lead_from_memory(ctx: RuntimeContext, stored: MemoryUpdate) -> RuntimeContext:
    """Fill in lead context gaps from stored memory. Normalizes lead_summary
    to remove any accumulated duplicate fragments before enriching."""
    lead = ctx.lead
    updates: dict = {}

    normalized_summary = _normalize_summary(stored.lead_summary)

    for field, value in [
        ("lead_summary", normalized_summary),
        ("last_intent", stored.last_intent),
        ("goal", stored.goal),
        ("interest_area", stored.interest_area),
        ("stage", stored.stage),
        ("last_messages_summary", stored.last_messages_summary),
    ]:
        if not getattr(lead, field, None) and value:
            updates[field] = value

    if stored.pain_points and not lead.pain_points:
        updates["pain_points"] = stored.pain_points

    if not updates:
        return ctx

    return ctx.model_copy(update={"lead": lead.model_copy(update=updates)})
