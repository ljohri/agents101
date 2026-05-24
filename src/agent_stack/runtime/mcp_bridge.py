"""MCP bridge (in-process tools for v0.1)."""

from __future__ import annotations

from typing import Any

from agent_stack.runtime.capabilities import InvocationContext
from agent_stack.tools import filesystem_safe


class McpBridge:
    def __init__(self) -> None:
        self._tools = dict(filesystem_safe.TOOLS)

    async def call(
        self, server_id: str, tool_name: str, inputs: dict[str, Any], ctx: InvocationContext
    ) -> Any:
        if server_id != "filesystem-safe":
            raise RuntimeError(f"mcp server {server_id!r} not available in v0.1 in-process bridge")
        fn = self._tools.get(tool_name)
        if fn is None:
            raise RuntimeError(f"unknown tool {tool_name!r} on {server_id}")
        return await fn(**inputs)

    def list_capabilities(self) -> list[str]:
        return [f"mcp.filesystem-safe.{name}" for name in self._tools]
