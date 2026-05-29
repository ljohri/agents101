"""LLM-as-planner: synthesize a capability-constrained plan."""

from __future__ import annotations

from root_agent.catalog import Catalog
from root_agent.llm.base import BaseLLMClient, complete_json
from root_agent.memory.schema import MemoryContext
from root_agent.planner.schema import Plan

_SYSTEM = """You are the planner for a local agent runtime.
Given a user request and a list of available capabilities, produce an ordered
plan of steps that fulfills the request. Honor user/project preferences in the
provided memory.

Rules:
- Each step's "call" MUST be one of the provided capability URIs verbatim.
  Forms: agent.<id>.<skill>, mcp.<server>.<tool>, command.<name>.
- Put step arguments under "with". Reference earlier results with
  {{ steps.<step_id>.<output_name> }} templating where useful.
- Prefer the fewest steps that correctly accomplish the task.
- Do not invent capabilities that are not listed."""


class PlannerError(RuntimeError):
    """Raised when the synthesized plan references unknown capabilities."""


class Planner:
    def __init__(self, llm: BaseLLMClient) -> None:
        self.llm = llm

    async def plan(self, request: str, catalog: Catalog, memory: MemoryContext) -> Plan:
        user = (
            f"User request:\n{request}\n\n"
            f"Memory:\n{memory.to_prompt_block()}\n\n"
            f"Available capabilities:\n{catalog.render_capabilities()}"
        )
        plan = await complete_json(self.llm, _SYSTEM, user, Plan)
        self._validate(plan, catalog)
        return plan

    @staticmethod
    def _validate(plan: Plan, catalog: Catalog) -> None:
        allowed = catalog.capability_uris()
        unknown = [step.call for step in plan.steps if step.call not in allowed]
        if unknown:
            raise PlannerError(f"plan references capabilities not in the catalog: {unknown}")
        if not plan.steps:
            raise PlannerError("planner returned an empty plan")
