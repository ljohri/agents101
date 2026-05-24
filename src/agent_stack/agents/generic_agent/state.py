"""Generic agent state."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class GenericState(TypedDict):
    tenant_id: str
    agent_id: str
    conversation_id: str
    user_message: str
    selected_skill: NotRequired[str]
    final_response: NotRequired[str]
