"""Direct workflow executor (v0.1 — no LangGraph required)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from agent_stack.registry.config import LoadedConfig
from agent_stack.registry.schemas import (
    StepAssign,
    StepBranch,
    StepCall,
    StepEmitArtifact,
    StepHumanApproval,
    StepParallel,
)
from agent_stack.runtime.capabilities import (
    CapabilityCall,
    CapabilityRegistry,
    CapabilityResult,
    InvocationContext,
)
from agent_stack.runtime.otel import start_span
from agent_stack.runtime.workflows.expressions import _AttrDict, render_value

InvokeFn = Callable[[CapabilityCall, InvocationContext], Awaitable[CapabilityResult]]


class WorkflowExecutor:
    def __init__(self, config: LoadedConfig, registry: CapabilityRegistry) -> None:
        self.config = config
        self.registry = registry

    async def run(
        self,
        workflow_id: str,
        inputs: dict[str, Any],
        ctx: InvocationContext,
        invoke_fn: InvokeFn,
    ) -> dict[str, Any]:
        wf = self.config.workflows.workflows[workflow_id]
        state: dict[str, Any] = {"inputs": inputs, "steps": {}}

        try:
            with start_span(
                "workflow.started",
                **{"workflow.id": workflow_id, "workflow.version": wf.version},
            ):
                for step in wf.steps:
                    step_ctx = ctx.model_copy(
                        update={
                            "workflow_id": workflow_id,
                            "workflow_version": wf.version,
                            "step_id": step.id,
                        }
                    )
                    should_run = step.when is None or bool(render_value(step.when, state))
                    if not should_run:
                        with start_span(
                            "workflow.step.entered",
                            **{
                                "workflow.id": workflow_id,
                                "workflow.version": wf.version,
                                "workflow.step_id": step.id,
                                "skipped": True,
                            },
                        ):
                            pass
                        continue

                    with start_span(
                        "workflow.step.entered",
                        **{
                            "workflow.id": workflow_id,
                            "workflow.version": wf.version,
                            "workflow.step_id": step.id,
                        },
                    ):
                        if isinstance(step, StepCall):
                            rendered = render_value(step.with_, state)
                            call = CapabilityCall(
                                uri=step.call,
                                inputs=rendered if isinstance(rendered, dict) else {"value": rendered},
                                idempotency_key=step.idempotency_key,
                                timeout_seconds=step.timeout_seconds,
                            )
                            result = await invoke_fn(call, step_ctx)
                            if not result.ok:
                                raise RuntimeError(result.error.message if result.error else "step failed")
                            if step.output:
                                state["steps"].setdefault(step.id, {})[step.output] = result.output

                        elif isinstance(step, StepAssign):
                            rendered = render_value(step.values, state)
                            state["steps"][step.id] = rendered

                        elif isinstance(step, StepHumanApproval):
                            approval_id = uuid.uuid4().hex
                            state["steps"][step.id] = {
                                "approval_id": approval_id,
                                "status": "pending",
                                "message": step.message,
                            }
                            with start_span(
                                "workflow.approval.requested",
                                **{
                                    "workflow.id": workflow_id,
                                    "workflow.version": wf.version,
                                    "workflow.step_id": step.id,
                                    "approval_id": approval_id,
                                },
                            ):
                                pass

                        elif isinstance(step, StepParallel):
                            items = render_value(step.for_each, state) if step.for_each else []
                            results = []
                            if step.call and items:
                                for item in items:
                                    item_val = _AttrDict(item) if isinstance(item, dict) else item
                                    item_scope = {**state, step.as_ or "item": item_val}
                                    rendered = render_value(step.with_ or {}, item_scope)
                                    call = CapabilityCall(uri=step.call, inputs=rendered)
                                    result = await invoke_fn(call, step_ctx)
                                    results.append(result.output if result.ok else {"error": True})
                            if step.output:
                                state["steps"].setdefault(step.id, {})[step.output] = results

                        elif isinstance(step, StepBranch):
                            target = step.default
                            for case in step.cases:
                                if render_value(case.when, state):
                                    target = case.goto
                                    break
                            state["steps"][step.id] = {"goto": target}

                        elif isinstance(step, StepEmitArtifact):
                            state["steps"][step.id] = {
                                "path": render_value(step.path, state),
                                "content": render_value(step.content, state) if step.content else None,
                            }

                        with start_span(
                            "workflow.step.completed",
                            **{
                                "workflow.id": workflow_id,
                                "workflow.version": wf.version,
                                "workflow.step_id": step.id,
                            },
                        ):
                            pass

            output = render_value(wf.output, state) if wf.output else state
            with start_span(
                "workflow.completed",
                **{"workflow.id": workflow_id, "workflow.version": wf.version},
            ):
                return output if isinstance(output, dict) else {"result": output}
        except Exception:
            with start_span(
                "workflow.failed",
                **{"workflow.id": workflow_id, "workflow.version": wf.version},
            ):
                pass
            raise


def exposed_skill_map(config: LoadedConfig) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for wf_id, wf in config.workflows.workflows.items():
        if wf.exposed_as_skill:
            mapping[wf.exposed_as_skill.id] = wf_id
    return mapping
