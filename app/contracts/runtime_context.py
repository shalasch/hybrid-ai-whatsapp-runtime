from typing import Any, Literal
from pydantic import BaseModel, Field

MessageType = Literal["text", "interactive", "unknown"]

class LeadContext(BaseModel):
    id: str | None = None
    nome: str | None = None
    interesse: str | None = None
    status: str | None = None
    lead_summary: str | None = None
    last_intent: str | None = None
    goal: str | None = None
    interest_area: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    stage: str | None = None
    last_messages_summary: str | None = None

class ConversationContext(BaseModel):
    id: str | None = None
    etapa: str | None = None
    status: str | None = None
    session_id: str | None = None

class MessageContext(BaseModel):
    text: str | None = None
    type: MessageType = "unknown"
    payload: str | None = None
    idempotency_key: str | None = None

class RoutingContext(BaseModel):
    action: str | None = None
    previous_action: str | None = None

class RuntimeContext(BaseModel):
    lead: LeadContext = Field(default_factory=LeadContext)
    conversation: ConversationContext = Field(default_factory=ConversationContext)
    message: MessageContext = Field(default_factory=MessageContext)
    routing: RoutingContext = Field(default_factory=RoutingContext)
    metadata: dict[str, Any] = Field(default_factory=dict)

class DecideRequest(BaseModel):
    runtime_context: RuntimeContext
