"""Outbound A2A client (minimal v0.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from agent_stack.registry.config import LoadedConfig
from agent_stack.registry.schemas import AgentRuntimeRemote
from agent_stack.runtime.capabilities import CapabilityError, CapabilityResult, InvocationContext


@dataclass
class CircuitState:
    failures: int = 0
    open: bool = False


class A2AClient:
    def __init__(self, config: LoadedConfig) -> None:
        self.config = config
        self._circuits: dict[str, CircuitState] = {}

    def remote_status(self) -> dict[str, Any]:
        out = {}
        for agent_id, agent in self.config.agents.agents.items():
            if agent.runtime.kind != "remote":
                continue
            out[agent_id] = {"circuit_open": self._circuits.get(agent_id, CircuitState()).open}
        return out

    async def send_message(
        self,
        remote_id: str,
        skill: str | None,
        inputs: dict[str, Any],
        conversation_id: str,
        ctx: InvocationContext,
    ) -> CapabilityResult:
        agent = self.config.agents.agents.get(remote_id)
        if agent is None or agent.runtime.kind != "remote":
            return CapabilityResult(
                uri=f"agent.{remote_id}.{skill or 'default'}",
                ok=False,
                error=CapabilityError(code="capability.not_found", message="remote agent missing", retryable=False),
            )
        rt: AgentRuntimeRemote = agent.runtime
        circuit = self._circuits.setdefault(remote_id, CircuitState())
        if circuit.open:
            return CapabilityResult(
                uri=f"agent.{remote_id}.{skill or 'default'}",
                ok=False,
                error=CapabilityError(code="capability.unavailable", message="circuit open", retryable=True),
            )

        token_env = rt.remote.auth.token_env
        headers = {"traceparent": f"00-{ctx.trace_id}-01"}
        if token_env:
            token = os.getenv(token_env, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        url = f"{rt.remote.base_url.rstrip('/')}{rt.remote.a2a_endpoint}"
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "conversation_id": conversation_id,
                "skill": skill,
                "inputs": inputs,
                "metadata": {"trace_id": ctx.trace_id},
            },
        }
        res = rt.remote.resilience
        timeout = httpx.Timeout(res.connect_timeout_seconds, read=res.read_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                circuit.failures = 0
                return CapabilityResult(
                    uri=f"agent.{remote_id}.{skill or 'default'}",
                    ok=True,
                    output=data.get("result"),
                    trace_id=ctx.trace_id,
                )
        except Exception as exc:
            circuit.failures += 1
            if circuit.failures >= rt.remote.resilience.circuit_breaker["failure_threshold"]:
                circuit.open = True
            return CapabilityResult(
                uri=f"agent.{remote_id}.{skill or 'default'}",
                ok=False,
                error=CapabilityError(code="capability.upstream_error", message=str(exc), retryable=True),
                trace_id=ctx.trace_id,
            )
