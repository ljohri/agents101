"""Bibliography agent graph."""

from __future__ import annotations

from typing import Any

from agent_stack.agents.bibliography_agent.tools import (
    extract_bibliography,
    resolve_open_access_pdfs,
    summarize_paper,
)


async def run_skill(skill_id: str, inputs: dict[str, Any]) -> Any:
    if skill_id == "extract-bibliography":
        return await extract_bibliography(str(inputs.get("input", inputs)))
    if skill_id == "resolve-open-access-pdfs":
        refs = inputs.get("references") or inputs.get("input") or []
        return await resolve_open_access_pdfs(refs)
    if skill_id == "summarize-paper":
        return await summarize_paper(str(inputs.get("input", inputs)))
    raise ValueError(f"unknown skill {skill_id!r}")


def build_graph(config, runtime_services):  # noqa: ANN001
    return run_skill
