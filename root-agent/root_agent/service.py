"""RootAgentService — wires the pieces and runs one request end to end.

Keeps the HTTP layer thin: routes call into this orchestrator. Construction is
side-effect free; call :meth:`startup` to load recipes and discover agents.
The LLM is built lazily and tolerantly so read-only endpoints (agents,
commands, status) work even when no LLM credentials are configured.
"""

from __future__ import annotations

import uuid
from typing import Any

from root_agent.a2a_client import A2AClient
from root_agent.catalog import build_catalog
from root_agent.commands.exec import CommandExecutor
from root_agent.commands.registry import CommandRegistry
from root_agent.config import RootAgentConfig
from root_agent.discovery import DiscoveryRegistry
from root_agent.llm.base import BaseLLMClient
from root_agent.llm.factory import build_llm
from root_agent.mcp import RootMcp
from root_agent.memory.retriever import MemoryRetriever
from root_agent.memory.store import MemoryStore
from root_agent.planner.executor import Executor
from root_agent.planner.judge import Judge
from root_agent.planner.planner import Planner
from root_agent.settings import Settings


class RootAgentService:
    def __init__(self, settings: Settings, config: RootAgentConfig, *, llm: BaseLLMClient | None = None) -> None:
        self.settings = settings
        self.config = config

        self.client = A2AClient(
            settings.runtime_base_url,
            bearer_token=settings.runtime_bearer_token,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.discovery = DiscoveryRegistry(self.client)

        self.command_registry = CommandRegistry(
            config.commands.dirs, allow_local_commands=settings.allow_local_commands
        )
        self.command_executor = CommandExecutor(
            self.command_registry, allow_local_commands=settings.allow_local_commands
        )

        self.memory_store = MemoryStore(
            settings.global_memory_path,
            settings.local_memory_path,
            enable_session=settings.enable_session_memory,
        )
        self.memory = MemoryRetriever(self.memory_store, max_chars=settings.memory_max_chars)

        self.mcp = RootMcp()

        # LLM is optional at construction; injected (tests) or built lazily.
        self.llm = llm
        self.llm_error: str | None = None
        self.judge: Judge | None = Judge(llm) if llm else None
        self.planner: Planner | None = Planner(llm) if llm else None

        self.executor = Executor(
            self.client,
            workflows_endpoint=config.runtime.workflows_endpoint,
            command_executor=self.command_executor,
            mcp_caller=self.mcp.caller(),
        )

    async def startup(self) -> None:
        """Load recipes and perform an initial discovery pass."""
        self.command_registry.load()
        if self.llm is None:
            self._build_llm()
        await self.discovery.refresh()

    def _build_llm(self) -> None:
        try:
            self.llm = build_llm(self.settings)
            self.judge = Judge(self.llm)
            self.planner = Planner(self.llm)
            self.llm_error = None
        except Exception as exc:  # noqa: BLE001 - surfaced via /status and /invoke
            self.llm_error = str(exc)

    async def refresh_discovery(self) -> None:
        await self.discovery.refresh()

    def _catalog(self):
        return build_catalog(
            self.discovery,
            command_capabilities=self.command_registry.capability_entries(),
            mcp_capabilities=self.mcp.capability_entries(),
        )

    async def handle_request(
        self,
        request: str,
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Judge -> (workflow | plan) -> execute, with memory injected."""
        if self.judge is None or self.planner is None:
            return {"ok": False, "error": f"LLM not configured: {self.llm_error or 'no provider'}"}

        conversation_id = conversation_id or uuid.uuid4().hex
        inputs = inputs or {}
        memory = self.memory.build_context(request, conversation_id)
        catalog = self._catalog()

        decision = await self.judge.decide(request, catalog, memory)
        if decision.decision == "use_workflow" and decision.workflow_id:
            result = await self.executor.run_workflow(
                decision.workflow_id, inputs, memory, conversation_id=conversation_id, trace_id=conversation_id
            )
            payload = {"mode": "workflow", "workflow_id": decision.workflow_id}
        else:
            plan = await self.planner.plan(request, catalog, memory)
            result = await self.executor.run_plan(
                plan, inputs, memory, conversation_id=conversation_id, trace_id=conversation_id
            )
            payload = {"mode": "plan", "plan": plan.model_dump(by_alias=True)}

        # Record what happened into session memory for continuity.
        self.memory_store.append(
            "session", f"Request: {request[:160]} -> {payload['mode']}", conversation_id=conversation_id
        )

        return {
            "ok": result.ok,
            "conversation_id": conversation_id,
            "decision": decision.model_dump(),
            **payload,
            "result": result.model_dump(),
        }

    # --- read-only views used by routes/CLI ---------------------------------

    def agents(self) -> list[dict]:
        return [a.model_dump() for a in self.discovery.agents()]

    def commands(self) -> list[dict]:
        return self.command_registry.availability()

    async def status(self) -> dict:
        return {
            "ok": True,
            "runtime_base_url": self.settings.runtime_base_url,
            "runtime_reachable": await self.client.healthz(),
            "llm_provider": self.settings.llm_provider,
            "llm_ready": self.judge is not None,
            "llm_error": self.llm_error,
            "memory_tiers": self.memory_store.tiers_loaded(),
            "mcp_available": self.mcp.available,
            "agents": len(self.discovery.agents()),
        }

    def remember(self, tier: str, note: str, conversation_id: str | None = None) -> dict:
        self.memory_store.append(tier, note, conversation_id=conversation_id)
        return {"ok": True, "tier": tier}
