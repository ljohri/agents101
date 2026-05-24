"""OpenClaw bridge (disabled by default)."""

from __future__ import annotations

from agent_stack.settings import Settings


class OpenClawBridge:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.openclaw_enabled

    async def invoke_agent(self, agent_id: str, message: str) -> dict:
        if not self.enabled:
            return {"status": "disabled", "message": "OpenClaw bridge disabled"}
        raise NotImplementedError("Verify local OpenClaw CLI invocation before enabling")

    async def health(self) -> dict:
        if not self.enabled:
            return {"ok": False, "reason": "disabled"}
        return {"ok": False, "reason": "not implemented"}
