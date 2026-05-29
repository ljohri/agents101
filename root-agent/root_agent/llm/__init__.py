"""LLM client abstraction for the root planner agent.

Providers are pluggable and lazily import their SDKs, so the package imports
cleanly even when a given SDK is not installed. Selection happens in
:func:`root_agent.llm.factory.build_llm` from settings.
"""

from root_agent.llm.base import BaseLLMClient, FakeLLMClient, LLMError, complete_json

__all__ = ["BaseLLMClient", "FakeLLMClient", "LLMError", "complete_json"]
