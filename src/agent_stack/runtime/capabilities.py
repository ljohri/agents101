"""Capability invocation envelope and registry."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from agent_stack.registry.config import LoadedConfig, _parse_uri


class CapabilityCall(BaseModel):
    uri: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    timeout_seconds: float | None = None
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityChunk(BaseModel):
    seq: int
    delta: Any
    done: bool = False


class CapabilityError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityResult(BaseModel):
    uri: str
    ok: bool
    output: Any | None = None
    error: CapabilityError | None = None
    trace_id: str = ""
    span_id: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0


class InvocationContext(BaseModel):
    tenant_id: str = "local"
    conversation_id: str = ""
    workflow_id: str | None = None
    workflow_version: str | None = None
    step_id: str | None = None
    cancel_token: Any = None
    bearer_token: str | None = None
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)


class CapabilityRegistry:
    def __init__(self, config: LoadedConfig) -> None:
        self.config = config
        self._idempotency: dict[str, CapabilityResult] = {}

    def list_uris(self) -> list[str]:
        uris: list[str] = []
        for agent in self.config.agents.agents.values():
            if agent.runtime.kind == "local":
                for skill in agent.skills:
                    uris.append(f"agent.{agent.id}.{skill.id}")
        for wf_id, wf in self.config.workflows.workflows.items():
            uris.append(f"workflow.{wf_id}")
            if wf.exposed_as_skill:
                uris.append(f"workflows.skill.{wf.exposed_as_skill.id}")
        for server_id, server in self.config.mcp_servers.servers.items():
            for tool in server.capabilities_filter.allow_tools or ["read_file", "write_file", "download_url"]:
                uris.append(f"mcp.{server_id}.{tool}")
        return sorted(set(uris))

    async def invoke(
        self,
        call: CapabilityCall,
        ctx: InvocationContext,
        *,
        agent_handler=None,
        mcp_handler=None,
        workflow_handler=None,
    ) -> CapabilityResult:
        started = time.perf_counter()
        trace_id = ctx.trace_id or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        if call.idempotency_key:
            key = hashlib.sha256(
                f"{ctx.tenant_id}:{call.uri}:{call.idempotency_key}".encode()
            ).hexdigest()
            cached = self._idempotency.get(key)
            if cached is not None:
                return cached.model_copy(update={"trace_id": trace_id, "span_id": span_id})

        try:
            scheme, parts = _parse_uri(call.uri)
        except Exception as exc:
            return self._fail(call.uri, "capability.invalid_uri", str(exc), trace_id, span_id, started)

        if call.stream:
            return self._fail(
                call.uri,
                "capability.streaming_unsupported",
                "streaming not implemented in v0.1 direct mode",
                trace_id,
                span_id,
                started,
            )

        try:
            if scheme == "agent":
                if agent_handler is None:
                    raise RuntimeError("agent handler not configured")
                output = await agent_handler(parts["agent_id"], parts["skill_id"], call.inputs, ctx)
            elif scheme == "mcp":
                if mcp_handler is None:
                    raise RuntimeError("mcp handler not configured")
                output = await mcp_handler(parts["mcp_server"], parts["mcp_tool"], call.inputs, ctx)
            elif scheme == "workflow":
                if workflow_handler is None:
                    raise RuntimeError("workflow handler not configured")
                output = await workflow_handler(parts["workflow_id"], call.inputs, ctx)
            elif scheme == "builtin":
                output = {"status": "ok", "builtin": parts["builtin_name"]}
            else:
                return self._fail(
                    call.uri, "capability.not_found", f"unknown scheme {scheme!r}", trace_id, span_id, started
                )
        except asyncio.CancelledError:
            return self._fail(call.uri, "capability.cancelled", "cancelled", trace_id, span_id, started)
        except TimeoutError:
            return self._fail(call.uri, "capability.timeout", "timeout", trace_id, span_id, started, retryable=True)
        except Exception as exc:
            return self._fail(
                call.uri, "capability.execution_error", str(exc), trace_id, span_id, started
            )

        result = CapabilityResult(
            uri=call.uri,
            ok=True,
            output=output,
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        if call.idempotency_key:
            self._idempotency[key] = result
        return result

    def _fail(
        self,
        uri: str,
        code: str,
        message: str,
        trace_id: str,
        span_id: str,
        started: float,
        *,
        retryable: bool = False,
    ) -> CapabilityResult:
        return CapabilityResult(
            uri=uri,
            ok=False,
            error=CapabilityError(code=code, message=message, retryable=retryable),
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


async def invoke(
    registry: CapabilityRegistry,
    uri: str,
    inputs: dict[str, Any],
    ctx: InvocationContext,
    **handlers,
) -> CapabilityResult:
    return await registry.invoke(CapabilityCall(uri=uri, inputs=inputs), ctx, **handlers)
