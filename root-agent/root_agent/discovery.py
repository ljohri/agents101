"""Discovery and health for downstream agents.

The root agent learns which agents exist by reading the runtime's aggregate
agent card, then probes each endpoint to report up/down status. This is what
backs the ``GET /agents`` endpoint and the CLI ``agents`` command.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from root_agent.a2a_client import A2AClient


class AgentInfo(BaseModel):
    id: str
    name: str
    url: str
    endpoint: str
    skills: list[dict] = Field(default_factory=list)
    is_workflows: bool = False
    status: str = "unknown"  # up | down | unknown
    last_checked: str | None = None
    error: str | None = None


def _endpoint_from_url(url: str) -> str:
    """Extract the path (A2A endpoint) from a full agent URL."""
    parsed = urlparse(url)
    return parsed.path or url


class DiscoveryRegistry:
    """Caches discovered agents and their last-probed status."""

    def __init__(self, client: A2AClient) -> None:
        self.client = client
        self._agents: dict[str, AgentInfo] = {}

    def agents(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def workflows_agent(self) -> AgentInfo | None:
        return next((a for a in self._agents.values() if a.is_workflows), None)

    async def refresh(self) -> list[AgentInfo]:
        """Re-read the aggregate card and probe each agent for liveness."""
        try:
            card = await self.client.get_card()
        except Exception as exc:
            # Runtime unreachable: keep prior cache but mark everything down.
            for info in self._agents.values():
                info.status = "down"
                info.error = str(exc)
                info.last_checked = _now()
            return self.agents()

        discovered: dict[str, AgentInfo] = {}
        for entry in card.get("agents", []):
            url = entry.get("url", "")
            endpoint = _endpoint_from_url(url)
            is_workflows = "workflows" in url
            agent_id = endpoint.rstrip("/").split("/")[-1] or entry.get("name", "agent")
            discovered[agent_id] = AgentInfo(
                id=agent_id,
                name=entry.get("name", agent_id),
                url=url,
                endpoint=endpoint,
                skills=entry.get("skills", []),
                is_workflows=is_workflows,
            )

        # Probe each agent via a cheap JSON-RPC agent/card call.
        for info in discovered.values():
            info.status, info.error = await self._probe(info)
            info.last_checked = _now()

        self._agents = discovered
        return self.agents()

    async def _probe(self, info: AgentInfo) -> tuple[str, str | None]:
        try:
            data = await self.client.rpc(info.endpoint, "agent/card", {})
            if data.get("error"):
                return "down", str(data["error"])
            return "up", None
        except Exception as exc:
            return "down", str(exc)


def _now() -> str:
    return datetime.now(UTC).isoformat()
