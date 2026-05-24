"""Root AGENTS.md generation."""

from __future__ import annotations

from agent_stack.registry.config import LoadedConfig


def build_agents_md(config: LoadedConfig) -> str:
    lines = [
        "# AGENTS.md",
        "",
        "Generated from local registry files. Prefer editing your private `agents.yaml` "
        "(gitignored; copy from `agents.yaml.example`).",
        "",
        "## Local Agent Stack",
        "",
        "This repository implements a shared local agent runtime using:",
        "",
        "- A2A for agent discovery and invocation.",
        "- MCP tools via the capability registry.",
        "- Declarative workflows in private `workflows.yaml`.",
        "",
        "## Registered Agents",
        "",
    ]
    for agent in config.agents.agents.values():
        if agent.runtime.kind != "local":
            continue
        lines.extend(
            [
                f"### {agent.name}",
                "",
                agent.description.strip(),
                "",
            ]
        )
        if agent.server:
            base = agent.server.base_url.rstrip("/")
            lines.append(f"A2A endpoint: `{base}{agent.server.a2a_endpoint}`")
            lines.append("")
        if agent.behavior and agent.behavior.rules:
            lines.append("Operating rules:")
            lines.append("")
            for rule in agent.behavior.rules:
                lines.append(f"- {rule}")
            lines.append("")

    exposed = [
        (wf_id, wf)
        for wf_id, wf in config.workflows.workflows.items()
        if wf.exposed_as_skill
    ]
    if exposed:
        lines.extend(["## Exposed Workflows", ""])
        for wf_id, wf in exposed:
            skill = wf.exposed_as_skill.id if wf.exposed_as_skill else wf_id
            lines.append(f"- `{skill}` — {wf.name} (workflow `{wf_id}`)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
