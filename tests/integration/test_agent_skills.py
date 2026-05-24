"""Agent skill integration tests."""

from __future__ import annotations

import pytest

from agent_stack.registry.config import load_all
from agent_stack.runtime.a2a_client import A2AClient
from agent_stack.runtime.capabilities import CapabilityRegistry, InvocationContext
from agent_stack.runtime.graph_runner import GraphRunner
from agent_stack.runtime.mcp_bridge import McpBridge
from tests.conftest import REPO_ROOT


@pytest.fixture
def runner():
    config = load_all(REPO_ROOT)
    registry = CapabilityRegistry(config)
    mcp = McpBridge()
    client = A2AClient(config)
    return GraphRunner(config, registry, mcp, client)


@pytest.mark.asyncio
async def test_bibliography_extract(runner: GraphRunner) -> None:
    ctx = InvocationContext(conversation_id="conv-test")
    result = await runner.run_agent_task(
        "bibliography",
        "conv-test",
        "extract-bibliography",
        {"input": "./data/paper.pdf"},
        ctx,
    )
    assert result.ok
    assert result.output is not None
