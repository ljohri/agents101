"""Root-agent-owned MCP access.

Reuses ``agent_stack``'s ``McpBridge`` when it is importable (the common case
when the root agent runs from the same repo), so MCP tools surface as
``mcp.<server>.<tool>`` capabilities the planner can call directly. If
``agent_stack`` is not on the path, MCP is disabled gracefully rather than
breaking import.
"""

from __future__ import annotations

from typing import Any


class RootMcp:
    def __init__(self, *, enabled: bool = True) -> None:
        self.available = False
        self.error: str | None = None
        self._bridge: Any = None
        self._ctx_cls: Any = None
        if enabled:
            self._try_init()
        else:
            self.error = "disabled"

    def _try_init(self) -> None:
        try:
            from agent_stack.runtime.capabilities import InvocationContext
            from agent_stack.runtime.mcp_bridge import McpBridge

            self._bridge = McpBridge()
            self._ctx_cls = InvocationContext
            self.available = True
        except Exception as exc:  # noqa: BLE001 - import or init failure is non-fatal
            self.error = f"agent_stack MCP bridge unavailable: {exc}"
            self.available = False

    async def call(self, server: str, tool: str, inputs: dict[str, Any]) -> Any:
        if not self.available:
            raise RuntimeError(self.error or "root MCP not available")
        ctx = self._ctx_cls()
        return await self._bridge.call(server, tool, inputs, ctx)

    def caller(self):
        """Return the executor-compatible MCP caller, or None when disabled."""
        return self.call if self.available else None

    def capability_entries(self) -> list:
        """Capabilities for the catalog (empty when MCP is unavailable)."""
        if not self.available:
            return []
        from root_agent.catalog import CapabilityEntry

        return [
            CapabilityEntry(uri=uri, kind="mcp", description="root-owned MCP tool")
            for uri in self._bridge.list_capabilities()
        ]
