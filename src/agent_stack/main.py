"""FastAPI entrypoint.

v0.1 scope: only healthcheck + config preload. The A2A surface is added in
Phase 3 (docs/build-plan.md sec 6).
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from .registry.config import ConfigError, LoadedConfig, load_all

logger = logging.getLogger("agent_stack.main")


def create_app(root: str | None = None) -> FastAPI:
    """Build a FastAPI app with config preloaded onto app.state.config.

    `root` defaults to the current working directory; override for tests.
    """
    app = FastAPI(title="agent-stack", version="0.1.0")
    config: LoadedConfig | None = None
    config_error: str | None = None
    try:
        config = load_all(root or os.getcwd())
    except ConfigError as exc:
        # In v0.1 we still serve /healthz so ops can probe; the error surfaces
        # in the body. Future phases will refuse to start.
        config_error = str(exc)
        logger.warning("config load failed: %s", exc)

    app.state.config = config
    app.state.config_error = config_error

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok" if config else "degraded",
            "config_loaded": config is not None,
            "config_error": config_error,
        }

    return app


app = create_app()
