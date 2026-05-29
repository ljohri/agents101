"""LLM client interface and structured-output helpers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised on provider/config errors (missing creds, SDK, or bad output)."""


class BaseLLMClient(ABC):
    """Minimal contract every provider implements: free-form completion."""

    model: str

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        """Return the model's text response."""
        raise NotImplementedError


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a single JSON object from model output.

    Handles bare JSON, fenced ```json blocks, and leading/trailing prose.
    """
    text = text.strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    # Fall back to the first balanced { ... } span.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def complete_json(client: BaseLLMClient, system: str, user: str, schema: type[T]) -> T:
    """Ask the client for JSON and validate it against ``schema``.

    The JSON schema is appended to the system prompt to steer the model toward
    a parseable, well-shaped response.
    """
    instructed = (
        f"{system}\n\nRespond with ONLY a JSON object that conforms to this JSON schema "
        f"(no prose, no markdown fences):\n{json.dumps(schema.model_json_schema())}"
    )
    raw = await client.complete(instructed, user)
    try:
        data = _extract_json(raw)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"LLM did not return valid JSON: {exc}\n---\n{raw[:500]}") from exc
    return schema.model_validate(data)


class FakeLLMClient(BaseLLMClient):
    """Deterministic client for tests and offline runs.

    Returns queued responses in order (or a fixed response). Lets the judge,
    planner, executor, and HTTP layer be exercised without any network/SDK.
    """

    def __init__(self, responses: list[str] | str, model: str = "fake") -> None:
        self.model = model
        self._responses = [responses] if isinstance(responses, str) else list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append((system, user))
        if not self._responses:
            raise LLMError("FakeLLMClient ran out of queued responses")
        # Repeat the last response once exhausted to tolerate extra calls.
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
