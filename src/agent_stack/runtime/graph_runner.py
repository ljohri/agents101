"""Graph runner — dispatches agent skills and workflows."""

from __future__ import annotations

import importlib
from typing import Any

from agent_stack.registry.config import LoadedConfig
from agent_stack.registry.schemas import AgentRuntimeLocal
from agent_stack.runtime.a2a_client import A2AClient
from agent_stack.runtime.capabilities import (
    CapabilityCall,
    CapabilityRegistry,
    CapabilityResult,
    InvocationContext,
)
from agent_stack.runtime.mcp_bridge import McpBridge
from agent_stack.runtime.workflows.executor import WorkflowExecutor, exposed_skill_map


class GraphRunner:
    def __init__(
        self,
        config: LoadedConfig,
        registry: CapabilityRegistry,
        mcp: McpBridge,
        a2a_client: A2AClient,
    ) -> None:
        self.config = config
        self.registry = registry
        self.mcp = mcp
        self.a2a_client = a2a_client
        self.workflow_executor = WorkflowExecutor(config, registry)
        self._agent_handlers: dict[str, Any] = {}
        self._skill_map = exposed_skill_map(config)

    def _load_agent_handler(self, agent_id: str):
        if agent_id in self._agent_handlers:
            return self._agent_handlers[agent_id]
        agent = self.config.agents.agents[agent_id]
        if agent.runtime.kind != "local":
            self._agent_handlers[agent_id] = None
            return None
        rt: AgentRuntimeLocal = agent.runtime
        mod = importlib.import_module(rt.module)
        factory = getattr(mod, rt.factory)
        handler = factory(self.config, {})
        self._agent_handlers[agent_id] = handler
        return handler

    async def _agent_handler(self, agent_id: str, skill_id: str, inputs: dict, ctx: InvocationContext) -> Any:
        agent = self.config.agents.agents[agent_id]
        if agent.runtime.kind == "remote":
            result = await self.a2a_client.send_message(agent_id, skill_id, inputs, ctx.conversation_id, ctx)
            if not result.ok:
                raise RuntimeError(result.error.message if result.error else "remote call failed")
            return result.output
        handler = self._load_agent_handler(agent_id)
        if handler is None:
            raise RuntimeError(f"agent {agent_id} has no local handler")
        return await handler(skill_id, inputs)

    async def _mcp_handler(self, server: str, tool: str, inputs: dict, ctx: InvocationContext) -> Any:
        return await self.mcp.call(server, tool, inputs, ctx)

    async def _workflow_handler(self, workflow_id: str, inputs: dict, ctx: InvocationContext) -> Any:
        async def invoke_fn(call: CapabilityCall, inner_ctx: InvocationContext) -> CapabilityResult:
            return await self.registry.invoke(
                call,
                inner_ctx,
                agent_handler=self._agent_handler,
                mcp_handler=self._mcp_handler,
                workflow_handler=self._workflow_handler,
            )

        return await self.workflow_executor.run(workflow_id, inputs, ctx, invoke_fn)

    async def run_agent_task(
        self,
        agent_id: str,
        conversation_id: str,
        skill: str | None,
        inputs: dict[str, Any] | None,
        ctx: InvocationContext,
    ) -> CapabilityResult:
        if agent_id == "workflows" and skill:
            wf_id = self._skill_map.get(skill)
            if wf_id is None:
                return CapabilityResult(
                    uri=f"workflow.{skill}",
                    ok=False,
                    error=None,
                )
            call = CapabilityCall(uri=f"workflow.{wf_id}", inputs=inputs or {})
            return await self.registry.invoke(
                call,
                ctx,
                workflow_handler=self._workflow_handler,
            )
        if skill is None:
            raise ValueError("skill required for agent dispatch")
        call = CapabilityCall(uri=f"agent.{agent_id}.{skill}", inputs=inputs or {})
        return await self.registry.invoke(
            call,
            ctx,
            agent_handler=self._agent_handler,
            mcp_handler=self._mcp_handler,
            workflow_handler=self._workflow_handler,
        )
