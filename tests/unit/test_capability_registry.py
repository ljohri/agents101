"""Capability registry unit tests."""

from __future__ import annotations

import pytest

from agent_stack.registry.config import load_all
from agent_stack.runtime.capabilities import CapabilityCall, CapabilityRegistry, InvocationContext
from tests.conftest import REPO_ROOT


@pytest.fixture
def registry() -> CapabilityRegistry:
    return CapabilityRegistry(load_all(REPO_ROOT))


def test_list_uris(registry: CapabilityRegistry) -> None:
    uris = registry.list_uris()
    assert "agent.bibliography.extract-bibliography" in uris
    assert "workflow.bibliography_research" in uris


@pytest.mark.asyncio
async def test_invoke_builtin(registry: CapabilityRegistry) -> None:
    ctx = InvocationContext(conversation_id="c1")
    result = await registry.invoke(
        CapabilityCall(uri="builtin.assign", inputs={}),
        ctx,
    )
    assert result.ok


@pytest.mark.asyncio
async def test_invalid_uri(registry: CapabilityRegistry) -> None:
    ctx = InvocationContext(conversation_id="c1")
    result = await registry.invoke(
        CapabilityCall(uri="not-valid", inputs={}),
        ctx,
    )
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "capability.invalid_uri"
