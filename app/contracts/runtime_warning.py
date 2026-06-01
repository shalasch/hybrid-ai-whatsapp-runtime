from typing import Literal
from pydantic import BaseModel

WarningSeverity = Literal["info", "warning", "error"]

WarningCode = Literal[
    "LOW_CONFIDENCE",
    "SENSITIVE_INTENT",
    "DUPLICATE_QUIZ",
    "INVALID_ROUTING_ACTION",
    "EMPTY_MESSAGE_BODY",
    "STATE_BLOCKED",
    "RETRIEVAL_FAILED",
    "HUMAN_ESCALATION",
    "VALIDATION_OVERRIDE",
    "FALLBACK_RESPONSE",
]


class RuntimeWarning(BaseModel):
    code: WarningCode
    severity: WarningSeverity
    source_node: str
    description: str
