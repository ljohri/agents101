"""A2A agent card generation."""

from __future__ import annotations

from typing import Any

from agent_stack.registry.config import LoadedConfig

SECRET_KEYS = {
    "token",
    "secret",
    "password",
    "api_key",
    "private_key",
    "refresh_token",
    "client_secret",
    "service_account",
    "bearer",
    "credentials",
}


def _skill_dict(skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "tags": skill.tags,
    }


def build_agent_card(config: LoadedConfig) -> dict[str, Any]:
    """Aggregate card for local agents + synthetic workflows agent."""
    agents_block: list[dict[str, Any]] = []
    for agent in config.agents.agents.values():
        if agent.runtime.kind != "local":
            continue
        base = agent.server.base_url if agent.server else config.agents.runtime.default_base_url
        endpoint = agent.server.a2a_endpoint if agent.server else f"/a2a/{agent.id}"
        agents_block.append(
            {
                "name": agent.name,
                "description": agent.description,
                "version": agent.version,
                "url": f"{base.rstrip('/')}{endpoint}",
                "provider": {"organization": (agent.owner.organization if agent.owner else "local-dev")},
                "capabilities": {
                    "streaming": bool(agent.capabilities and agent.capabilities.streaming),
                    "pushNotifications": bool(agent.capabilities and agent.capabilities.push_notifications),
                    "stateTransitionHistory": bool(
                        agent.capabilities and agent.capabilities.state_transition_history
                    ),
                },
                "authentication": {"schemes": ["bearer"]},
                "skills": [_skill_dict(s) for s in agent.skills],
            }
        )

    wf_skills = []
    for wf in config.workflows.workflows.values():
        if wf.exposed_as_skill:
            wf_skills.append(
                {
                    "id": wf.exposed_as_skill.id,
                    "name": wf.name,
                    "description": wf.description or wf.name,
                    "tags": wf.exposed_as_skill.tags,
                }
            )
    if wf_skills:
        base = config.agents.runtime.default_base_url
        agents_block.append(
            {
                "name": "local-workflows-agent",
                "description": "Synthetic agent exposing compiled workflows as skills.",
                "version": "0.1.0",
                "url": f"{base.rstrip('/')}/a2a/workflows",
                "provider": {"organization": "local-dev"},
                "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": True},
                "authentication": {"schemes": ["bearer"]},
                "skills": wf_skills,
            }
        )

    primary = agents_block[0] if agents_block else {
        "name": "agent-stack",
        "description": "Local agent stack",
        "version": "0.1.0",
        "url": config.agents.runtime.default_base_url,
        "skills": [],
        "authentication": {"schemes": ["bearer"]},
    }
    card = {**primary, "agents": agents_block}
    return _strip_secrets(card)


def _strip_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_secrets(v) for k, v in obj.items() if k.lower() not in SECRET_KEYS}
    if isinstance(obj, list):
        return [_strip_secrets(v) for v in obj]
    return obj
