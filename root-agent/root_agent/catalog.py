"""Catalog: the single view of options the LLM reasons over.

Merges three sources into prompt-ready structures:
- workflows (the runtime's exposed ``workflows`` agent skills) for the judge,
- capabilities (agent skills + local commands) for the planner.

MCP tools owned by the root agent are appended as ``mcp.<server>.<tool>`` when a
root MCP bridge is configured. Memory is passed alongside the catalog rather
than embedded, so retrieval can evolve independently.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from root_agent.discovery import DiscoveryRegistry


class WorkflowEntry(BaseModel):
    skill_id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)


class CapabilityEntry(BaseModel):
    uri: str  # agent.<id>.<skill> | command.<name> | mcp.<server>.<tool>
    kind: str  # agent | command | mcp
    description: str = ""


class Catalog(BaseModel):
    workflows: list[WorkflowEntry] = Field(default_factory=list)
    capabilities: list[CapabilityEntry] = Field(default_factory=list)

    def workflow_ids(self) -> set[str]:
        return {w.skill_id for w in self.workflows}

    def capability_uris(self) -> set[str]:
        return {c.uri for c in self.capabilities}

    def render_workflows(self) -> str:
        if not self.workflows:
            return "(no workflows available)"
        return "\n".join(f"- {w.skill_id}: {w.name} — {w.description}" for w in self.workflows)

    def render_capabilities(self) -> str:
        if not self.capabilities:
            return "(no capabilities available)"
        return "\n".join(f"- {c.uri} [{c.kind}]: {c.description}".rstrip() for c in self.capabilities)


def build_catalog(
    registry: DiscoveryRegistry,
    *,
    command_capabilities: list[CapabilityEntry] | None = None,
    mcp_capabilities: list[CapabilityEntry] | None = None,
) -> Catalog:
    """Assemble the catalog from discovered agents + local commands + MCP."""
    workflows: list[WorkflowEntry] = []
    capabilities: list[CapabilityEntry] = []

    for agent in registry.agents():
        if agent.is_workflows:
            # The synthetic workflows agent exposes each workflow as a skill.
            for skill in agent.skills:
                workflows.append(
                    WorkflowEntry(
                        skill_id=skill.get("id", ""),
                        name=skill.get("name", skill.get("id", "")),
                        description=skill.get("description", ""),
                        tags=skill.get("tags", []),
                    )
                )
            continue
        # Only advertise capabilities for agents currently reachable.
        if agent.status == "down":
            continue
        for skill in agent.skills:
            sid = skill.get("id", "")
            capabilities.append(
                CapabilityEntry(
                    uri=f"agent.{agent.id}.{sid}",
                    kind="agent",
                    description=skill.get("description", skill.get("name", sid)),
                )
            )

    capabilities.extend(command_capabilities or [])
    capabilities.extend(mcp_capabilities or [])
    return Catalog(workflows=workflows, capabilities=capabilities)
