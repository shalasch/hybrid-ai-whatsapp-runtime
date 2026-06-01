import uuid
from fastapi import APIRouter, HTTPException
from langsmith import tracing_context
from app.config import settings
from app.contracts.runtime_context import DecideRequest
from app.contracts.decision_output import DecideResponse
from app.graph.builder import build_decision_graph
from app.memory.store import upsert_memory
from app.observability.audit_logger import build_audit_record, log_decision_audit
from app.observability.logger import logger

router = APIRouter(tags=["decision-runtime"])
graph = build_decision_graph()


@router.post("/decide", response_model=DecideResponse)
async def decide(payload: DecideRequest) -> DecideResponse:
    ctx = payload.runtime_context
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"

    log = logger.bind(
        trace_id=trace_id,
        lead_id=ctx.lead.id,
        conversation_id=ctx.conversation.id,
        session_id=ctx.conversation.session_id,
        idempotency_key=ctx.message.idempotency_key,
    )
    log.info("AI_DECISION_REQUEST_RECEIVED")

    try:
        with tracing_context(enabled=settings.langsmith_tracing, project_name=settings.langsmith_project):
            result = graph.invoke({
                "runtime_context": ctx,
                "trace_id": trace_id,
                "warnings": [],
                "debug": {},
            })

        decision: DecideResponse = result["decision"]

        if decision.memory_update:
            upsert_memory(ctx.lead.id, ctx.conversation.id, decision.memory_update)

        audit = build_audit_record(
            trace_id=trace_id,
            lead_id=ctx.lead.id,
            conversation_id=ctx.conversation.id,
            user_message=ctx.message.text,
            detected_intent=result.get("intent"),
            routing_action=decision.routing_action,
            confidence=decision.confidence,
            needs_human=decision.needs_human,
            retrieval_used=decision.retrieval.used,
            retrieval_sources=decision.retrieval.sources,
            runtime_warnings=decision.runtime_warnings,
        )
        log_decision_audit(audit)

        log.info(
            "AI_DECISION_COMPLETED",
            routing_action=decision.routing_action,
            confidence=decision.confidence,
            needs_human=decision.needs_human,
            warning_count=len(decision.runtime_warnings),
            structured_warning_count=len(decision.structured_warnings),
        )
        return decision

    except Exception as exc:
        log.exception("AI_DECISION_ERROR", error=str(exc))
        raise HTTPException(status_code=500, detail="AI decision runtime failed safely") from exc
