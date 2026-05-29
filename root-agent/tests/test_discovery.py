import asyncio

from root_agent.a2a_client import A2AClient
from root_agent.catalog import build_catalog
from root_agent.discovery import DiscoveryRegistry

CARD = {
    "agents": [
        {"name": "bib", "url": "http://x/a2a/bibliography", "skills": [{"id": "extract", "description": "d"}]},
        {
            "name": "wf",
            "url": "http://x/a2a/workflows",
            "skills": [{"id": "bibliography-research", "name": "Bib", "description": "research"}],
        },
    ]
}


class FakeClient(A2AClient):
    def __init__(self, card, up=True):
        super().__init__("http://x")
        self._card = card
        self._up = up

    async def get_card(self):
        return self._card

    async def rpc(self, endpoint, method, params=None, *, trace_id=None):
        return {"result": {}} if self._up else {"error": "down"}


def test_discovery_marks_agents_up_and_finds_workflows():
    reg = DiscoveryRegistry(FakeClient(CARD))
    agents = asyncio.run(reg.refresh())
    ids = {a.id for a in agents}
    assert {"bibliography", "workflows"} <= ids
    assert reg.workflows_agent().is_workflows is True
    assert all(a.status == "up" for a in agents)


def test_discovery_marks_down_on_probe_failure():
    reg = DiscoveryRegistry(FakeClient(CARD, up=False))
    agents = asyncio.run(reg.refresh())
    assert all(a.status == "down" for a in agents)


def test_discovery_handles_unreachable_runtime():
    class Down(A2AClient):
        def __init__(self):
            super().__init__("http://x")

        async def get_card(self):
            raise RuntimeError("connection refused")

    reg = DiscoveryRegistry(Down())
    assert asyncio.run(reg.refresh()) == []


def test_catalog_splits_workflows_and_capabilities():
    reg = DiscoveryRegistry(FakeClient(CARD))
    asyncio.run(reg.refresh())
    cat = build_catalog(reg)
    assert "bibliography-research" in cat.workflow_ids()
    assert "agent.bibliography.extract" in cat.capability_uris()
