"""Generic agent graph (direct handler for v0.1)."""

from __future__ import annotations

from typing import Any

from agent_stack.agents.generic_agent.tools import echo


async def run_skill(skill_id: str, inputs: dict[str, Any]) -> Any:
    if skill_id == "echo":
        msg = inputs.get("message") or inputs.get("input") or str(inputs)
        return await echo(str(msg))
    raise ValueError(f"unknown skill {skill_id!r}")


def build_graph(config, runtime_services):  # noqa: ANN001 — LangGraph hook for later
    return run_skill
