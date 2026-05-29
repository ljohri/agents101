"""Execute a chosen workflow or a synthesized plan.

Two entry points:
- :meth:`Executor.run_workflow` delegates to the runtime's ``workflows`` agent
  over A2A, passing memory via ``metadata.memory_context``.
- :meth:`Executor.run_plan` runs synthesized steps, dispatching:
  - ``agent.<id>.<skill>``  -> A2A message/send to ``/a2a/<id>``
  - ``mcp.<server>.<tool>`` -> the optional MCP caller
  - ``command.<name>``      -> the guarded local command executor

Step arguments support ``{{ inputs.* }}``, ``{{ steps.<id>.<name> }}`` and
``{{ memory }}`` templating against the running state.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from root_agent.a2a_client import A2AClient
from root_agent.commands.exec import CommandExecutor
from root_agent.memory.schema import MemoryContext
from root_agent.planner.schema import Plan, PlanStep

# An MCP caller: (server, tool, inputs) -> tool output. Optional.
MCPCaller = Callable[[str, str, dict[str, Any]], Awaitable[Any]]

_EXPR = re.compile(r"{{\s*(.*?)\s*}}")


class StepResult(BaseModel):
    id: str
    call: str
    ok: bool
    output: Any | None = None
    error: str | None = None


class ExecutionResult(BaseModel):
    ok: bool
    mode: str  # "workflow" | "plan"
    detail: str = ""  # workflow id or plan rationale
    output: Any | None = None
    steps: list[StepResult] = Field(default_factory=list)
    error: str | None = None


def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            break
    return cur


def render(value: Any, ctx: dict[str, Any]) -> Any:
    """Render templated values, preserving type for a lone ``{{ expr }}``."""
    if isinstance(value, dict):
        return {k: render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    if isinstance(value, str):
        whole = _EXPR.fullmatch(value.strip())
        if whole:
            return _lookup(whole.group(1), ctx)
        return _EXPR.sub(lambda m: str(_lookup(m.group(1), ctx)), value)
    return value


class Executor:
    def __init__(
        self,
        a2a_client: A2AClient,
        *,
        workflows_endpoint: str = "/a2a/workflows",
        command_executor: CommandExecutor | None = None,
        mcp_caller: MCPCaller | None = None,
    ) -> None:
        self.client = a2a_client
        self.workflows_endpoint = workflows_endpoint
        self.commands = command_executor
        self.mcp_caller = mcp_caller

    async def run_workflow(
        self,
        workflow_skill_id: str,
        inputs: dict[str, Any],
        memory: MemoryContext,
        *,
        conversation_id: str | None = None,
        trace_id: str | None = None,
    ) -> ExecutionResult:
        result = await self.client.message_send(
            self.workflows_endpoint,
            skill=workflow_skill_id,
            inputs=inputs,
            conversation_id=conversation_id,
            metadata=memory.to_metadata(),
            trace_id=trace_id,
        )
        return ExecutionResult(
            ok=result.ok,
            mode="workflow",
            detail=workflow_skill_id,
            output=result.content,
            error=result.error,
        )

    async def run_plan(
        self,
        plan: Plan,
        inputs: dict[str, Any],
        memory: MemoryContext,
        *,
        conversation_id: str | None = None,
        trace_id: str | None = None,
    ) -> ExecutionResult:
        state: dict[str, Any] = {"inputs": inputs, "steps": {}, "memory": memory.merged}
        steps: list[StepResult] = []

        for step in plan.steps:
            rendered = render(step.with_, state)
            args = rendered if isinstance(rendered, dict) else {"value": rendered}
            sr = await self._run_step(step, args, memory, conversation_id, trace_id)
            steps.append(sr)
            if not sr.ok:
                return ExecutionResult(
                    ok=False, mode="plan", detail=plan.rationale, steps=steps,
                    error=f"step {step.id!r} failed: {sr.error}",
                )
            # Make the output addressable for later steps.
            if step.output:
                state["steps"].setdefault(step.id, {})[step.output] = sr.output
            else:
                state["steps"][step.id] = sr.output

        output = render(plan.output, state) if plan.output else (steps[-1].output if steps else None)
        return ExecutionResult(ok=True, mode="plan", detail=plan.rationale, output=output, steps=steps)

    async def _run_step(
        self,
        step: PlanStep,
        args: dict[str, Any],
        memory: MemoryContext,
        conversation_id: str | None,
        trace_id: str | None,
    ) -> StepResult:
        scheme, _, rest = step.call.partition(".")
        try:
            if scheme == "agent":
                agent_id, _, skill = rest.partition(".")
                res = await self.client.message_send(
                    f"/a2a/{agent_id}",
                    skill=skill,
                    inputs=args,
                    conversation_id=conversation_id,
                    metadata=memory.to_metadata(),
                    trace_id=trace_id,
                )
                return StepResult(id=step.id, call=step.call, ok=res.ok, output=res.content, error=res.error)

            if scheme == "workflow":
                res = await self.client.message_send(
                    self.workflows_endpoint, skill=rest, inputs=args,
                    conversation_id=conversation_id, metadata=memory.to_metadata(), trace_id=trace_id,
                )
                return StepResult(id=step.id, call=step.call, ok=res.ok, output=res.content, error=res.error)

            if scheme == "mcp":
                if self.mcp_caller is None:
                    return StepResult(id=step.id, call=step.call, ok=False, error="MCP not configured on root agent")
                server, _, tool = rest.partition(".")
                out = await self.mcp_caller(server, tool, args)
                return StepResult(id=step.id, call=step.call, ok=True, output=out)

            if scheme == "command":
                if self.commands is None:
                    return StepResult(id=step.id, call=step.call, ok=False, error="commands not configured")
                cmd = await self.commands.run(rest, args)
                output = cmd.stdout if cmd.ok else None
                return StepResult(id=step.id, call=step.call, ok=cmd.ok, output=output, error=cmd.error)

            return StepResult(id=step.id, call=step.call, ok=False, error=f"unknown capability scheme {scheme!r}")
        except Exception as exc:  # noqa: BLE001
            return StepResult(id=step.id, call=step.call, ok=False, error=str(exc))
