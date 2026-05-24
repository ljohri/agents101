"""Thin audit facade over storage."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from agent_stack.runtime.storage import insert_audit


class AuditLogger:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def a2a_received(self, agent_id: str, conversation_id: str, method: str, trace_id: str) -> None:
        insert_audit(
            self.engine,
            "a2a.request.received",
            agent_id=agent_id,
            conversation_id=conversation_id,
            trace_id=trace_id,
            payload={"method": method},
        )

    def a2a_sent(self, agent_id: str, conversation_id: str, ok: bool, trace_id: str) -> None:
        insert_audit(
            self.engine,
            "a2a.response.sent",
            agent_id=agent_id,
            conversation_id=conversation_id,
            trace_id=trace_id,
            payload={"ok": ok},
        )

    def capability(self, event_type: str, uri: str, conversation_id: str, trace_id: str, **payload) -> None:
        insert_audit(
            self.engine,
            event_type,
            capability_uri=uri,
            conversation_id=conversation_id,
            trace_id=trace_id,
            payload=payload,
        )
