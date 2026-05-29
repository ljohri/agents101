"""Vertex AI (Gemini) client authenticated via a service-account file.

When ``LLM_PROVIDER=vertex``, credentials come from the service-account JSON at
``GOOGLE_APPLICATION_CREDENTIALS`` (the google SDK reads it automatically) plus
``VERTEX_PROJECT`` / ``VERTEX_LOCATION``.
"""

from __future__ import annotations

import os

from root_agent.llm.base import BaseLLMClient, LLMError


class VertexGeminiClient(BaseLLMClient):
    def __init__(
        self,
        model: str,
        project: str,
        location: str,
        credentials_path: str | None = None,
    ) -> None:
        self.model = model
        self._project = project
        self._location = location
        self._credentials_path = credentials_path

    async def complete(self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        # The Vertex SDK is synchronous; run it without blocking the event loop.
        import asyncio

        return await asyncio.to_thread(self._complete_sync, system, user, max_tokens, temperature)

    def _complete_sync(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "google-cloud-aiplatform not installed; `pip install google-cloud-aiplatform`"
            ) from exc

        # The SDK reads GOOGLE_APPLICATION_CREDENTIALS from the environment; set
        # it here when an explicit path was provided in settings.
        if self._credentials_path:
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", self._credentials_path)

        vertexai.init(project=self._project, location=self._location)
        model = GenerativeModel(self.model, system_instruction=system)
        resp = model.generate_content(
            user,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return resp.text or ""
