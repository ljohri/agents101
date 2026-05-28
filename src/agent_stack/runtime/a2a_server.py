"""A2A JSON-RPC server routes."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from agent_stack.registry.agent_card import build_agent_card
from agent_stack.runtime.a2a_client import A2AClient
from agent_stack.runtime.audit import AuditLogger
from agent_stack.runtime.capabilities import CapabilityRegistry, InvocationContext
from agent_stack.runtime.graph_runner import GraphRunner
from agent_stack.runtime.observability import inc, log_event, render_metrics
from agent_stack.runtime.otel import current_trace_ids, extract_trace_context, start_span
from agent_stack.runtime.security import require_auth, require_localhost
from agent_stack.runtime.storage import insert_conversation, insert_message
from agent_stack.settings import Settings


def create_a2a_router(app) -> APIRouter:  # noqa: ANN001
    router = APIRouter()
    settings: Settings = app.state.settings
    config = app.state.config
    engine = app.state.engine
    audit: AuditLogger = app.state.audit
    registry: CapabilityRegistry = app.state.registry
    runner: GraphRunner = app.state.runner
    a2a_client: A2AClient = app.state.a2a_client

    card = build_agent_card(config)

    @router.get("/.well-known/agent-card.json")
    @router.get("/.well-known/agent.json")
    def get_card():
        return JSONResponse(card)

    @router.get("/admin/capabilities")
    def admin_capabilities(request: Request):
        require_localhost(request)
        return [{"uri": u} for u in registry.list_uris()]

    @router.get("/admin/remotes")
    def admin_remotes(request: Request):
        require_localhost(request)
        return a2a_client.remote_status()

    @router.post("/admin/reload")
    def admin_reload(request: Request):
        require_localhost(request)
        return {"status": "reload not implemented in v0.1; restart process"}

    @router.get(settings.metrics_path)
    def metrics(request: Request):
        require_localhost(request)
        if not settings.metrics_enabled:
            raise HTTPException(status_code=404)
        return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4")

    async def _handle_rpc(agent_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        require_auth(request, settings)
        method = body.get("method")
        params = body.get("params") or {}
        rpc_id = body.get("id", "1")
        conversation_id = params.get("conversation_id") or insert_conversation(engine, agent_id)
        metadata_trace_id = (params.get("metadata") or {}).get("trace_id")
        parent_context = extract_trace_context(dict(request.headers))
        attrs: dict[str, Any] = {
            "a2a.method": method or "unknown",
            "agent.id": agent_id,
            "conversation_id": conversation_id,
        }
        if metadata_trace_id:
            attrs["app.trace_id"] = metadata_trace_id

        with start_span("a2a.request.received", parent_context=parent_context, **attrs):
            trace_id, _ = current_trace_ids()
            if not trace_id:
                trace_id = metadata_trace_id or uuid.uuid4().hex
            ctx = InvocationContext(conversation_id=conversation_id, trace_id=trace_id)

            audit.a2a_received(agent_id, conversation_id, method, trace_id)
            inc("a2a_inbound_requests_total", {"method": method or "unknown", "agent_id": agent_id, "ok": "true"})

            if method == "agent/card":
                agent_cfg = next((a for a in config.agents.agents.values() if a.id == agent_id), None)
                if agent_id == "workflows":
                    result = next(a for a in card.get("agents", []) if "workflows" in a.get("url", ""))
                elif agent_cfg and agent_cfg.runtime.kind == "local":
                    result = next((a for a in card.get("agents", []) if a["name"] == agent_cfg.name), card)
                else:
                    result = card
            elif method == "skills/list":
                if agent_id == "workflows":
                    wf_agent = next(
                        a for a in card.get("agents", []) if "workflows" in a.get("url", "")
                    )
                    result = {"skills": wf_agent.get("skills", [])}
                else:
                    agent_cfg = config.agents.agents.get(agent_id)
                    if agent_cfg is None:
                        raise HTTPException(status_code=404, detail="agent not found")
                    result = {
                        "skills": [
                            {"id": s.id, "name": s.name, "description": s.description}
                            for s in agent_cfg.skills
                        ]
                    }
            elif method == "message/send":
                message = params.get("message") or {}
                skill = params.get("skill")
                inputs = params.get("inputs")
                if inputs is None and message:
                    inputs = {"message": message.get("content", "")}
                user_content = json.dumps(params)
                insert_message(engine, conversation_id, "user", user_content)
                cap_result = await runner.run_agent_task(agent_id, conversation_id, skill, inputs, ctx)
                if not cap_result.ok:
                    with start_span("a2a.response.sent", **attrs, ok=False):
                        audit.a2a_sent(agent_id, conversation_id, False, trace_id)
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32000,
                            "message": cap_result.error.message if cap_result.error else "failed",
                        },
                    }
                content = cap_result.output if isinstance(cap_result.output, str) else json.dumps(cap_result.output)
                insert_message(engine, conversation_id, "agent", content)
                with start_span("a2a.response.sent", **attrs, ok=True):
                    audit.a2a_sent(agent_id, conversation_id, True, trace_id)
                log_event("a2a.response.sent", agent_id=agent_id, conversation_id=conversation_id, trace_id=trace_id)
                result = {"conversation_id": conversation_id, "role": "agent", "content": content, "artifacts": []}
            else:
                raise HTTPException(status_code=400, detail=f"unsupported method {method!r}")

            return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    @router.post("/a2a/{agent_id}")
    async def a2a_agent(agent_id: str, request: Request):
        body = await request.json()
        return await _handle_rpc(agent_id, body, request)

    @router.post("/a2a")
    async def a2a_default(request: Request):
        default = next(iter(config.agents.agents.values()))
        body = await request.json()
        return await _handle_rpc(default.id, body, request)

    return router
