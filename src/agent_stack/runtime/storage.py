"""App DB storage (sync SQLAlchemy for v0.1 simplicity)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_stack.settings import Settings


def _ensure_parent(url: str) -> None:
    if url.startswith("sqlite:///./"):
        path = Path(url.removeprefix("sqlite:///./"))
        path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(settings: Settings) -> Engine:
    _ensure_parent(settings.app_database_url)
    return create_engine(settings.app_database_url, future=True)


def init_db(engine: Engine, schema_path: Path | None = None) -> None:
    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[3] / "scripts" / "sql" / "app_schema.sql"
    ddl = schema_path.read_text()
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def insert_conversation(engine: Engine, agent_id: str, conversation_id: str | None = None) -> str:
    cid = conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO conversations (id, tenant_id, agent_id, created_at, updated_at) "
                "VALUES (:id, 'local', :agent_id, :now, :now)"
            ),
            {"id": cid, "agent_id": agent_id, "now": now},
        )
    return cid


def insert_message(engine: Engine, conversation_id: str, role: str, content: str) -> None:
    now = datetime.now(UTC).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, role, content, created_at) "
                "VALUES (:id, :cid, :role, :content, :now)"
            ),
            {"id": uuid.uuid4().hex, "cid": conversation_id, "role": role, "content": content, "now": now},
        )


def insert_audit(
    engine: Engine,
    event_type: str,
    *,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    capability_uri: str | None = None,
    trace_id: str | None = None,
    payload: dict | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_events (id, tenant_id, agent_id, conversation_id, capability_uri, "
                "trace_id, event_type, event_json, created_at) "
                "VALUES (:id, 'local', :agent_id, :cid, :uri, :trace, :etype, :payload, :now)"
            ),
            {
                "id": uuid.uuid4().hex,
                "agent_id": agent_id,
                "cid": conversation_id,
                "uri": capability_uri,
                "trace": trace_id,
                "etype": event_type,
                "payload": json.dumps(payload or {}),
                "now": now,
            },
        )
