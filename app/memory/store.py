import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.contracts.decision_output import MemoryUpdate

# Lazily initialized from settings; override directly in tests via monkeypatch.
_DB_PATH: Path | None = None


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        from app.config import settings
        _DB_PATH = Path(settings.memory_db_path)
    return _DB_PATH


def _connect() -> sqlite3.Connection:
    db = _get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_memory (
            lead_id               TEXT NOT NULL,
            conversation_id       TEXT NOT NULL,
            lead_summary          TEXT,
            last_intent           TEXT,
            goal                  TEXT,
            interest_area         TEXT,
            pain_points           TEXT,
            stage                 TEXT,
            last_messages_summary TEXT,
            updated_at            TEXT NOT NULL,
            PRIMARY KEY (lead_id, conversation_id)
        )
    """)
    conn.commit()


def get_memory(lead_id: str | None, conversation_id: str | None) -> MemoryUpdate | None:
    """Return stored memory for a lead/conversation pair, or None if not found."""
    if not lead_id or not conversation_id:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM lead_memory WHERE lead_id = ? AND conversation_id = ?",
            (lead_id, conversation_id),
        ).fetchone()
        if not row:
            return None
        return MemoryUpdate(
            lead_summary=row["lead_summary"],
            last_intent=row["last_intent"],
            goal=row["goal"],
            interest_area=row["interest_area"],
            pain_points=json.loads(row["pain_points"] or "[]"),
            stage=row["stage"],
            last_messages_summary=row["last_messages_summary"],
        )
    finally:
        conn.close()


def upsert_memory(
    lead_id: str | None,
    conversation_id: str | None,
    memory: MemoryUpdate,
) -> None:
    """Insert or update compact lead memory. Silent no-op if identifiers are missing."""
    if not lead_id or not conversation_id:
        return
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO lead_memory
                (lead_id, conversation_id, lead_summary, last_intent, goal,
                 interest_area, pain_points, stage, last_messages_summary, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id, conversation_id) DO UPDATE SET
                lead_summary          = excluded.lead_summary,
                last_intent           = excluded.last_intent,
                goal                  = excluded.goal,
                interest_area         = excluded.interest_area,
                pain_points           = excluded.pain_points,
                stage                 = excluded.stage,
                last_messages_summary = excluded.last_messages_summary,
                updated_at            = excluded.updated_at
            """,
            (
                lead_id,
                conversation_id,
                memory.lead_summary,
                memory.last_intent,
                memory.goal,
                memory.interest_area,
                json.dumps(memory.pain_points),
                memory.stage,
                memory.last_messages_summary,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
