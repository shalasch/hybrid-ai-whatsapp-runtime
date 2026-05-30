from typing import Any, TypedDict
from app.contracts.runtime_context import RuntimeContext
from app.contracts.decision_output import DecideResponse, MemoryUpdate
from app.rag.retriever import RetrievedDocument

class DecisionGraphState(TypedDict, total=False):
    runtime_context: RuntimeContext
    intent: str
    retrieved_docs: list[RetrievedDocument]
    memory_update: MemoryUpdate
    decision: DecideResponse
    warnings: list[str]
    debug: dict[str, Any]
