"""
Append-only JSONL audit log for runtime decision events.

Each record captures the full decision context — trace_id, intent, routing,
confidence, retrieval, and warnings — without storing message content beyond
what is explicitly included. Non-blocking: failures are logged, never raised.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.observability.logger import logger


def _get_path() -> Path:
    from app.config import settings
    return Path(settings.audit_log_path)


def log_decision_audit(record: dict) -> None:
    """Write one audit record to the JSONL log. Safe to call from async context."""
    try:
        path = _get_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.warning("AUDIT_LOG_WRITE_FAILED", error=str(exc))


def build_audit_record(
    *,
    trace_id: str,
    lead_id: str | None,
    conversation_id: str | None,
    user_message: str | None,
    detected_intent: str | None,
    routing_action: str,
    confidence: float,
    needs_human: bool,
    retrieval_used: bool,
    retrieval_sources: list[str],
    runtime_warnings: list[str],
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "lead_id": lead_id,
        "conversation_id": conversation_id,
        "user_message": user_message,
        "detected_intent": detected_intent,
        "routing_action": routing_action,
        "confidence": confidence,
        "needs_human": needs_human,
        "retrieval_used": retrieval_used,
        "retrieval_sources": retrieval_sources,
        "runtime_warnings": runtime_warnings,
    }
