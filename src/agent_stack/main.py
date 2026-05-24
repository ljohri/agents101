"""FastAPI entrypoint."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from agent_stack.registry.config import ConfigError, LoadedConfig, load_all
from agent_stack.runtime.a2a_client import A2AClient
from agent_stack.runtime.a2a_server import create_a2a_router
from agent_stack.runtime.audit import AuditLogger
from agent_stack.runtime.capabilities import CapabilityRegistry
from agent_stack.runtime.graph_runner import GraphRunner
from agent_stack.runtime.mcp_bridge import McpBridge
from agent_stack.runtime.openclaw_bridge import OpenClawBridge
from agent_stack.runtime.storage import get_engine, init_db
from agent_stack.settings import load_settings

logger = logging.getLogger("agent_stack.main")


def create_app(root: str | None = None) -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="agent-stack", version="0.1.0")

    config: LoadedConfig | None = None
    config_error: str | None = None
    try:
        config = load_all(root or os.getcwd())
    except ConfigError as exc:
        config_error = str(exc)
        logger.warning("config load failed: %s", exc)

    app.state.settings = settings
    app.state.config = config
    app.state.config_error = config_error

    if config is not None:
        engine = get_engine(settings)
        init_db(engine)
        registry = CapabilityRegistry(config)
        mcp = McpBridge()
        a2a_client = A2AClient(config)
        runner = GraphRunner(config, registry, mcp, a2a_client)
        audit = AuditLogger(engine)
        app.state.engine = engine
        app.state.registry = registry
        app.state.mcp = mcp
        app.state.a2a_client = a2a_client
        app.state.runner = runner
        app.state.audit = audit
        app.state.openclaw = OpenClawBridge(settings)
        app.include_router(create_a2a_router(app))

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok" if config else "degraded",
            "config_loaded": config is not None,
            "config_error": config_error,
        }

    return app


# Lazy app for uvicorn; tests should call create_app() directly.
app = create_app()
