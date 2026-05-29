"""API-key LLM providers: OpenAI, Anthropic, and Gemini (API key).

Each provider lazily imports its dependency so importing this module never
requires the SDK to be installed.
"""

from __future__ import annotations

import httpx

from root_agent.llm.base import BaseLLMClient, LLMError


class OpenAIClient(BaseLLMClient):
    """OpenAI (and OpenAI-compatible) chat completions."""

    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url

    async def complete(self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - exercised only without SDK
            raise LLMError("openai SDK not installed; `pip install openai`") from exc

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        resp = await client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


class AnthropicClient(BaseLLMClient):
    """Anthropic messages API."""

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self._api_key = api_key

    async def complete(self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic SDK not installed; `pip install anthropic`") from exc

        client = AsyncAnthropic(api_key=self._api_key)
        resp = await client.messages.create(
            model=self.model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks.
        return "".join(getattr(block, "text", "") for block in resp.content)


class GeminiApiKeyClient(BaseLLMClient):
    """Gemini via the Generative Language REST API (API-key auth).

    Uses httpx directly to avoid pulling in an extra SDK; for Vertex (service
    account) auth use :class:`root_agent.llm.vertex.VertexGeminiClient`.
    """

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model: str, api_key: str, timeout_seconds: float = 30.0) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def complete(self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        url = f"{self.BASE}/{self.model}:generateContent?key={self._api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected Gemini response shape: {data}") from exc
