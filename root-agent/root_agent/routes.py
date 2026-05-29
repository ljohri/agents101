"""HTTP routes for the root planner agent.

Thin layer over :class:`root_agent.service.RootAgentService`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from root_agent.service import RootAgentService


class InvokeRequest(BaseModel):
    request: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None


class MemoryNote(BaseModel):
    tier: str = "global"  # global | local | session
    note: str
    conversation_id: str | None = None


def create_router(service: RootAgentService) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @router.get("/status")
    async def status() -> dict:
        return await service.status()

    @router.get("/agents")
    async def agents() -> dict:
        # Refresh on read so up/down reflects current reality.
        await service.refresh_discovery()
        return {"agents": service.agents()}

    @router.get("/commands")
    async def commands() -> dict:
        return {"commands": service.commands()}

    @router.post("/memory")
    async def memory(note: MemoryNote) -> dict:
        return service.remember(note.tier, note.note, note.conversation_id)

    @router.post("/invoke")
    async def invoke(req: InvokeRequest) -> dict:
        return await service.handle_request(req.request, req.inputs, req.conversation_id)

    @router.post("/a2a/root")
    async def a2a_root(request: Request) -> dict:
        """A2A-style entrypoint so the root agent is itself a valid A2A agent."""
        body = await request.json()
        params = body.get("params") or {}
        rpc_id = body.get("id", "1")
        text = params.get("inputs", {}).get("request") or (params.get("message") or {}).get("content", "")
        result = await service.handle_request(
            text, params.get("inputs") or {}, params.get("conversation_id")
        )
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    return router
