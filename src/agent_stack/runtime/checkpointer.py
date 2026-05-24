"""LangGraph checkpointer factory (optional)."""

from __future__ import annotations

from agent_stack.settings import Settings


def get_checkpointer(settings: Settings):
    if not settings.use_langgraph:
        return None
    if settings.langgraph_checkpointer == "memory":
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except ImportError as exc:
            raise RuntimeError("install langgraph extra: uv sync --extra langgraph") from exc
    if settings.langgraph_checkpointer == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            return SqliteSaver.from_conn_string(settings.langgraph_sqlite_path)
        except ImportError as exc:
            raise RuntimeError("install langgraph extra") from exc
    if settings.langgraph_checkpointer == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            return PostgresSaver.from_conn_string(settings.langgraph_postgres_dsn)
        except ImportError as exc:
            raise RuntimeError("install langgraph+postgres extras") from exc
    raise ValueError(f"unknown checkpointer {settings.langgraph_checkpointer!r}")
