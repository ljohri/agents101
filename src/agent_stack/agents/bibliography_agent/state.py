"""Bibliography agent state."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class BibliographyState(TypedDict):
    tenant_id: str
    agent_id: str
    conversation_id: str
    user_message: str
    selected_skill: NotRequired[str]
    extracted_references: NotRequired[list[dict]]
    resolved_metadata: NotRequired[list[dict]]
    final_response: NotRequired[str]
