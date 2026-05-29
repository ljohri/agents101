"""Build the configured LLM client from settings.

Selection is by ``LLM_PROVIDER``. API-key providers require ``LLM_API_KEY``;
Vertex requires project/location (and a service-account file via
``GOOGLE_APPLICATION_CREDENTIALS``). Missing credentials fail fast.
"""

from __future__ import annotations

from root_agent.llm.base import BaseLLMClient, FakeLLMClient, LLMError
from root_agent.llm.providers import AnthropicClient, GeminiApiKeyClient, OpenAIClient
from root_agent.llm.vertex import VertexGeminiClient
from root_agent.settings import Settings


def build_llm(settings: Settings) -> BaseLLMClient:
    provider = settings.llm_provider

    if provider == "fake":
        # Offline/testing provider; echoes an empty plan-shaped response.
        return FakeLLMClient(responses="{}", model=settings.llm_model)

    if provider in {"openai", "anthropic", "gemini"}:
        if not settings.llm_api_key:
            raise LLMError(f"LLM_PROVIDER={provider} requires LLM_API_KEY")
        if provider == "openai":
            return OpenAIClient(settings.llm_model, settings.llm_api_key, settings.llm_base_url)
        if provider == "anthropic":
            return AnthropicClient(settings.llm_model, settings.llm_api_key)
        return GeminiApiKeyClient(settings.llm_model, settings.llm_api_key)

    if provider == "vertex":
        if not settings.vertex_project:
            raise LLMError("LLM_PROVIDER=vertex requires VERTEX_PROJECT")
        if not settings.google_application_credentials:
            raise LLMError("LLM_PROVIDER=vertex requires GOOGLE_APPLICATION_CREDENTIALS (service-account file)")
        return VertexGeminiClient(
            settings.llm_model,
            project=settings.vertex_project,
            location=settings.vertex_location,
            credentials_path=settings.google_application_credentials,
        )

    raise LLMError(f"unknown LLM_PROVIDER {provider!r} (expected openai|anthropic|gemini|vertex|fake)")
