from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
from app.contracts.routing_actions import ALLOWED_ROUTING_ACTIONS, RoutingAction
from app.contracts.runtime_context import RuntimeContext
from app.contracts.runtime_warning import RuntimeWarning


class ReasoningTrace(BaseModel):
    intent: str | None = None
    matched_signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    decision_factors: list[str] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    lead_summary: str | None = None
    last_intent: str | None = None
    goal: str | None = None
    interest_area: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    stage: str | None = None
    last_messages_summary: str | None = None


class RetrievalInfo(BaseModel):
    used: bool = False
    sources: list[str] = Field(default_factory=list)
    top_scores: list[float] = Field(default_factory=list)
    embedding_provider: str | None = None


class DecideResponse(BaseModel):
    # Operational identifiers — required for downstream Airtable/handler execution
    lead_id: str | None = None
    conversation_id: str | None = None
    trace_id: str | None = None
    # Echo of the incoming context for n8n passthrough
    runtime_context: RuntimeContext | None = None

    routing_action: RoutingAction
    message_type: Literal["text", "interactive", "none"] = "text"
    message_body: str | None = None
    confidence: float = Field(ge=0, le=1)
    needs_human: bool = False
    reason: str
    reasoning: ReasoningTrace = Field(default_factory=ReasoningTrace)
    memory_update: MemoryUpdate = Field(default_factory=MemoryUpdate)
    retrieval: RetrievalInfo = Field(default_factory=RetrievalInfo)
    # Backward-compatible string warnings (unchanged)
    runtime_warnings: list[str] = Field(default_factory=list)
    # Structured warning taxonomy (additive — does not replace string warnings)
    structured_warnings: list[RuntimeWarning] = Field(default_factory=list)

    @field_validator("routing_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in ALLOWED_ROUTING_ACTIONS:
            raise ValueError(f"Unsupported routing_action: {value}")
        return value
