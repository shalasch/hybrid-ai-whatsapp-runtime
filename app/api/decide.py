from fastapi import APIRouter, HTTPException
from langsmith import tracing_context
from app.config import settings
from app.contracts.runtime_context import DecideRequest
from app.contracts.decision_output import DecideResponse
from app.graph.builder import build_decision_graph
from app.observability.logger import logger

router = APIRouter(tags=["decision-runtime"])
graph = build_decision_graph()

@router.post("/decide", response_model=DecideResponse)
async def decide(payload: DecideRequest) -> DecideResponse:
    ctx = payload.runtime_context
    log = logger.bind(
        lead_id=ctx.lead.id,
        conversation_id=ctx.conversation.id,
        session_id=ctx.conversation.session_id,
        idempotency_key=ctx.message.idempotency_key,
    )
    log.info("AI_DECISION_REQUEST_RECEIVED")
    try:
        with tracing_context(enabled=settings.langsmith_tracing, project_name=settings.langsmith_project):
            result = graph.invoke({"runtime_context": ctx, "warnings": [], "debug": {}})
        decision = result["decision"]
        log.info(
            "AI_DECISION_COMPLETED",
            routing_action=decision.routing_action,
            confidence=decision.confidence,
            needs_human=decision.needs_human,
            warnings=decision.runtime_warnings,
        )
        return decision
    except Exception as exc:
        log.exception("AI_DECISION_ERROR", error=str(exc))
        raise HTTPException(status_code=500, detail="AI decision runtime failed safely") from exc
