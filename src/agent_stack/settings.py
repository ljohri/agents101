"""Environment-backed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8080
    allow_dev_no_auth: bool = True
    allow_public_bind: bool = False
    local_agent_token: str = "change-me"
    app_database_url: str = "sqlite:///./data/agent.db"
    use_langgraph: bool = False
    langgraph_checkpointer: str = "memory"
    langgraph_sqlite_path: str = "./data/langgraph.db"
    langgraph_postgres_dsn: str = ""
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    openclaw_enabled: bool = False
    nemoclaw_enabled: bool = False


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8080")),
        allow_dev_no_auth=os.getenv("ALLOW_DEV_NO_AUTH", "true").lower() == "true",
        allow_public_bind=os.getenv("ALLOW_PUBLIC_BIND", "false").lower() == "true",
        local_agent_token=os.getenv("LOCAL_AGENT_TOKEN", "change-me"),
        app_database_url=os.getenv("APP_DATABASE_URL", "sqlite:///./data/agent.db"),
        use_langgraph=os.getenv("USE_LANGGRAPH", "false").lower() == "true",
        langgraph_checkpointer=os.getenv("LANGGRAPH_CHECKPOINTER", "memory"),
        langgraph_sqlite_path=os.getenv("LANGGRAPH_SQLITE_PATH", "./data/langgraph.db"),
        langgraph_postgres_dsn=os.getenv("LANGGRAPH_POSTGRES_DSN", ""),
        metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
        metrics_path=os.getenv("METRICS_PATH", "/metrics"),
        openclaw_enabled=os.getenv("OPENCLAW_ENABLED", "false").lower() == "true",
        nemoclaw_enabled=os.getenv("NEMOCLAW_ENABLED", "false").lower() == "true",
    )
