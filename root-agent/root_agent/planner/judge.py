"""LLM-as-judge: pick an existing workflow or escalate to planning."""

from __future__ import annotations

from root_agent.catalog import Catalog
from root_agent.llm.base import BaseLLMClient, complete_json
from root_agent.memory.schema import MemoryContext
from root_agent.planner.schema import JudgeDecision

_SYSTEM = """You are the routing judge for a local agent runtime.
Given a user request and a list of available deterministic workflows (each with
an id and description), decide whether one workflow already satisfies the
request. Respect any user/project preferences in the provided memory.

- If a workflow clearly fits, return decision "use_workflow" and its exact id.
- If none fits (or a custom multi-step plan is needed), return decision "plan".
Always include a short reason."""


class Judge:
    def __init__(self, llm: BaseLLMClient) -> None:
        self.llm = llm

    async def decide(self, request: str, catalog: Catalog, memory: MemoryContext) -> JudgeDecision:
        user = (
            f"User request:\n{request}\n\n"
            f"Memory:\n{memory.to_prompt_block()}\n\n"
            f"Available workflows:\n{catalog.render_workflows()}"
        )
        decision = await complete_json(self.llm, _SYSTEM, user, JudgeDecision)

        # Guardrail: never trust a workflow id that is not actually exposed.
        if decision.decision == "use_workflow":
            if not decision.workflow_id or decision.workflow_id not in catalog.workflow_ids():
                return JudgeDecision(
                    decision="plan",
                    reason=f"judge picked unknown workflow {decision.workflow_id!r}; falling back to planning",
                )
        return decision
