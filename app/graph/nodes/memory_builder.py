import time
from app.graph.state import DecisionGraphState
from app.memory.builder import build_memory_update, enrich_lead_from_memory
from app.memory.store import get_memory
from app.observability.logger import logger

_ENRICHABLE_FIELDS = (
    "lead_summary", "last_intent", "goal",
    "interest_area", "stage", "last_messages_summary", "pain_points",
)


def memory_builder(state: DecisionGraphState) -> DecisionGraphState:
    _start = time.monotonic()
    ctx = state["runtime_context"]
    intent = state.get("intent")

    stored = get_memory(ctx.lead.id, ctx.conversation.id)
    memory_loaded = stored is not None

    enriched_fields: list[str] = []
    if stored:
        original_lead = ctx.lead
        ctx = enrich_lead_from_memory(ctx, stored)
        enriched_fields = [
            f for f in _ENRICHABLE_FIELDS
            if getattr(original_lead, f, None) != getattr(ctx.lead, f, None)
        ]

    update = build_memory_update(ctx, intent, stored)
    duration_ms = round((time.monotonic() - _start) * 1000, 2)

    logger.info(
        "MEMORY_BUILDER_COMPLETED",
        node_name="memory_builder",
        memory_loaded=memory_loaded,
        enriched_fields=enriched_fields,
        intent=intent,
        duration_ms=duration_ms,
    )

    debug = {
        **state.get("debug", {}),
        "memory_builder": {
            "memory_loaded": memory_loaded,
            "enriched_fields": enriched_fields,
            "intent": intent,
            "duration_ms": duration_ms,
        },
    }

    return {**state, "runtime_context": ctx, "memory_update": update, "debug": debug}
