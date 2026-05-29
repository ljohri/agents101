import pytest

from root_agent.llm.base import FakeLLMClient, LLMError
from root_agent.llm.factory import build_llm
from root_agent.llm.providers import AnthropicClient, GeminiApiKeyClient, OpenAIClient
from root_agent.llm.vertex import VertexGeminiClient
from root_agent.settings import Settings


def test_fake_provider():
    assert isinstance(build_llm(Settings(llm_provider="fake")), FakeLLMClient)


def test_api_key_providers_require_key():
    for provider in ("openai", "anthropic", "gemini"):
        with pytest.raises(LLMError):
            build_llm(Settings(llm_provider=provider, llm_api_key=None))


def test_api_key_providers_build():
    assert isinstance(build_llm(Settings(llm_provider="openai", llm_api_key="k")), OpenAIClient)
    assert isinstance(build_llm(Settings(llm_provider="anthropic", llm_api_key="k")), AnthropicClient)
    assert isinstance(build_llm(Settings(llm_provider="gemini", llm_api_key="k")), GeminiApiKeyClient)


def test_vertex_requires_project_and_creds():
    with pytest.raises(LLMError):
        build_llm(Settings(llm_provider="vertex"))
    with pytest.raises(LLMError):
        build_llm(Settings(llm_provider="vertex", vertex_project="p"))


def test_vertex_builds_with_service_account():
    client = build_llm(
        Settings(llm_provider="vertex", vertex_project="p", google_application_credentials="/tmp/sa.json")
    )
    assert isinstance(client, VertexGeminiClient)


def test_unknown_provider():
    with pytest.raises(LLMError):
        build_llm(Settings(llm_provider="banana"))
