from __future__ import annotations

from pydantic import BaseModel, Field
from openai import OpenAI

from app.config import settings
from app.contracts.routing_actions import RoutingAction
from app.contracts.runtime_context import RuntimeContext
from app.rag.retriever import RetrievedDocument
from app.services.decision_prompt import build_messages
from app.observability.logger import logger


class AIDecisionResult(BaseModel):
    routing_action: RoutingAction
    message_body: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human: bool
    reason: str
    matched_signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class DecisionClient:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            max_retries=2,
            timeout=20.0,
        )
        self.model = settings.openai_model

    def get_decision(
        self,
        ctx: RuntimeContext,
        intent: str,
        docs: list[RetrievedDocument],
    ) -> AIDecisionResult:
        messages = build_messages(ctx, intent, docs)
        response = self._client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=AIDecisionResult,
            temperature=0.1,
            max_tokens=512,
        )
        result = response.choices[0].message.parsed
        if result is None:
            raise ValueError("OpenAI returned a null parsed result")
        logger.debug(
            "openai_decision_ok",
            routing_action=result.routing_action,
            confidence=result.confidence,
            model=self.model,
        )
        return result


_client: DecisionClient | None = None


def get_client() -> DecisionClient | None:
    """Return a shared DecisionClient, or None if OPENAI_API_KEY is not set."""
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        _client = DecisionClient()
    return _client
