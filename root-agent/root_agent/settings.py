"""Environment-backed settings for the root planner agent.

Settings hold secrets and per-deployment values loaded from the root agent's
own ``.env`` (separate from the agent_stack runtime). Structural, non-secret
configuration lives in ``config/root_agent.yaml`` (see :mod:`root_agent.config`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def expand_path(path: str | None) -> str | None:
    """Expand ``~`` and ``$VARS`` in a path; return None for empty input."""
    if not path:
        return None
    return str(Path(os.path.expandvars(os.path.expanduser(path))))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _opt(name: str) -> str | None:
    # Treat empty env values as "unset" so blank .env lines fall back to defaults.
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    # HTTP(S) entrypoint
    host: str = "127.0.0.1"
    port: int = 8443
    tls_certfile: str | None = None
    tls_keyfile: str | None = None

    # Downstream agent_stack runtime (reached over A2A loopback)
    runtime_base_url: str = "http://127.0.0.1:8086"
    runtime_bearer_token: str | None = None
    discovery_interval_seconds: float = 30.0
    request_timeout_seconds: float = 30.0

    # LLM provider
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str | None = None
    llm_base_url: str | None = None

    # Vertex AI / Gemini via service account file
    google_application_credentials: str | None = None
    vertex_project: str | None = None
    vertex_location: str = "us-central1"

    # Memory
    global_memory_path: str = "~/.root-agent/memory/GLOBAL.md"
    local_memory_path: str = "./.root-agent/memory/LOCAL.md"
    memory_max_chars: int = 4000
    enable_session_memory: bool = True

    # Commands
    commands_dir: str = "~/.root-agent/commands"
    local_commands_dir: str = "./.root-agent/commands"
    allow_local_commands: bool = True

    @property
    def tls_enabled(self) -> bool:
        """HTTPS is served only when both cert and key are provided."""
        return bool(self.tls_certfile and self.tls_keyfile)


def load_settings(env_file: str | None = None) -> Settings:
    """Build :class:`Settings` from the environment.

    ``env_file`` (defaults to ``./.env``) is loaded first so values defined
    there are visible via ``os.getenv``.
    """
    load_dotenv(env_file) if env_file else load_dotenv()

    return Settings(
        host=os.getenv("ROOT_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("ROOT_AGENT_PORT", "8443")),
        tls_certfile=expand_path(_opt("ROOT_AGENT_TLS_CERTFILE")),
        tls_keyfile=expand_path(_opt("ROOT_AGENT_TLS_KEYFILE")),
        runtime_base_url=os.getenv("RUNTIME_BASE_URL", "http://127.0.0.1:8086"),
        runtime_bearer_token=_opt("RUNTIME_BEARER_TOKEN"),
        discovery_interval_seconds=float(os.getenv("DISCOVERY_INTERVAL_SECONDS", "30")),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_api_key=_opt("LLM_API_KEY"),
        llm_base_url=_opt("LLM_BASE_URL"),
        google_application_credentials=expand_path(_opt("GOOGLE_APPLICATION_CREDENTIALS")),
        vertex_project=_opt("VERTEX_PROJECT"),
        vertex_location=os.getenv("VERTEX_LOCATION", "us-central1"),
        global_memory_path=os.getenv("ROOT_AGENT_GLOBAL_MEMORY", "~/.root-agent/memory/GLOBAL.md"),
        local_memory_path=os.getenv("ROOT_AGENT_LOCAL_MEMORY", "./.root-agent/memory/LOCAL.md"),
        memory_max_chars=int(os.getenv("ROOT_AGENT_MEMORY_MAX_CHARS", "4000")),
        enable_session_memory=_bool("ROOT_AGENT_ENABLE_SESSION_MEMORY", True),
        commands_dir=os.getenv("ROOT_AGENT_COMMANDS_DIR", "~/.root-agent/commands"),
        local_commands_dir=os.getenv("ROOT_AGENT_LOCAL_COMMANDS_DIR", "./.root-agent/commands"),
        allow_local_commands=_bool("ROOT_AGENT_ALLOW_LOCAL_COMMANDS", True),
    )
