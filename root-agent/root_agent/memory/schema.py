"""Memory data structures shared across the subsystem."""

from __future__ import annotations

from pydantic import BaseModel


class MemoryContext(BaseModel):
    """The relevant memory slice assembled for one request.

    ``merged`` is the prompt-ready text (already trimmed to the configured
    budget); the per-tier fields are retained for inspection and the
    ``/memory`` and ``/status`` endpoints.
    """

    global_text: str = ""
    local_text: str = ""
    session_text: str = ""
    merged: str = ""

    def is_empty(self) -> bool:
        return not (self.global_text or self.local_text or self.session_text)

    def to_prompt_block(self) -> str:
        """Render the memory for inclusion in an LLM prompt."""
        if self.is_empty():
            return "(no memory)"
        return self.merged

    def to_metadata(self) -> dict:
        """Compact form passed to fixed workflows via A2A ``metadata``."""
        return {"memory_context": self.merged}
