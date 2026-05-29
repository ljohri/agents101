"""FastAPI application for the root planner agent.

Run with:
    uv run uvicorn root_agent.main:app --host 127.0.0.1 --port 8443
or via ``python -m root_agent.main`` which honors TLS settings from .env.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI

from root_agent.config import load_config
from root_agent.routes import create_router
from root_agent.service import RootAgentService
from root_agent.settings import load_settings

logger = logging.getLogger("root_agent")


def create_app() -> FastAPI:
    settings = load_settings()
    config = load_config()
    service = RootAgentService(settings, config)

    app = FastAPI(title="root-agent", version="0.1.0")
    app.state.settings = settings
    app.state.service = service
    app.include_router(create_router(service))

    @app.on_event("startup")
    async def _on_startup() -> None:
        await service.startup()
        # Periodically refresh the up/down view in the background.
        app.state._discovery_task = asyncio.create_task(_discovery_loop(service))

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        task = getattr(app.state, "_discovery_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return app


async def _discovery_loop(service: RootAgentService) -> None:
    interval = service.settings.discovery_interval_seconds
    while True:
        await asyncio.sleep(interval)
        try:
            await service.refresh_discovery()
        except Exception as exc:  # noqa: BLE001
            logger.warning("discovery refresh failed: %s", exc)


app = create_app()


def serve() -> None:
    """Entrypoint that serves with HTTPS when TLS settings are present."""
    import uvicorn

    settings = load_settings()
    kwargs: dict = {"host": settings.host, "port": settings.port}
    if settings.tls_enabled:
        kwargs["ssl_certfile"] = settings.tls_certfile
        kwargs["ssl_keyfile"] = settings.tls_keyfile
    uvicorn.run("root_agent.main:app", **kwargs)


if __name__ == "__main__":
    serve()
