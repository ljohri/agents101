"""Generic outbound A2A client.

Unlike the agent_stack client (which only resolves agents declared
``kind: remote`` in ``agents.yaml``), this client talks to *any* A2A endpoint
addressed by ``base_url`` + ``endpoint``. The root agent uses it to reach the
runtime's synthetic ``workflows`` agent and the per-agent endpoints over an
HTTP loopback.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field


class A2AResult(BaseModel):
    """Normalized result of a JSON-RPC ``message/send`` call."""

    ok: bool
    content: Any | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class A2AClient:
    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.timeout = httpx.Timeout(timeout_seconds)

    def _headers(self, trace_id: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if trace_id:
            # Surfaced for cross-process correlation with the runtime's traces.
            headers["X-Trace-Id"] = trace_id
        return headers

    async def rpc(
        self,
        endpoint: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Low-level JSON-RPC call; returns the decoded response envelope."""
        url = f"{self.base_url}{endpoint}"
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers(trace_id))
            resp.raise_for_status()
            return resp.json()

    async def message_send(
        self,
        endpoint: str,
        *,
        skill: str | None = None,
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> A2AResult:
        """Send a ``message/send`` request and normalize the response.

        ``metadata`` is the channel used to pass memory context to fixed
        workflows without disturbing their declared input schema.
        """
        params: dict[str, Any] = {"skill": skill, "inputs": inputs or {}}
        if conversation_id:
            params["conversation_id"] = conversation_id
        if metadata:
            params["metadata"] = metadata
        try:
            data = await self.rpc(endpoint, "message/send", params, trace_id=trace_id)
        except Exception as exc:  # network / HTTP error
            return A2AResult(ok=False, error=str(exc))

        if "error" in data and data["error"]:
            return A2AResult(ok=False, raw=data, error=str(data["error"].get("message", data["error"])))
        result = data.get("result", {})
        content = result.get("content") if isinstance(result, dict) else result
        return A2AResult(ok=True, content=content, raw=data)

    async def get_card(self) -> dict[str, Any]:
        """Fetch the aggregate agent card from the runtime."""
        url = f"{self.base_url}/.well-known/agent-card.json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers(None))
            resp.raise_for_status()
            return resp.json()

    async def healthz(self) -> bool:
        """Return True if the runtime liveness endpoint responds 2xx."""
        url = f"{self.base_url}/healthz"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._headers(None))
                return resp.is_success
        except Exception:
            return False
