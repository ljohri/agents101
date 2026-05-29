"""Structural configuration loaded from ``config/root_agent.yaml``.

This is the non-secret companion to :mod:`root_agent.settings`. It describes
how the root agent is wired (runtime endpoints, planner behavior, memory tiers,
command dirs) without holding any credentials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class RuntimeConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8086"
    workflows_endpoint: str = "/a2a/workflows"
    discovery_interval_seconds: float = 30.0
    request_timeout_seconds: float = 30.0


class PlannerConfig(BaseModel):
    persist_synthesized_workflows: bool = False


class MemoryConfig(BaseModel):
    global_path: str = "~/.root-agent/memory/GLOBAL.md"
    local_path: str = "./.root-agent/memory/LOCAL.md"
    max_chars: int = 4000
    enable_session: bool = True


class CommandsConfig(BaseModel):
    dirs: list[str] = Field(default_factory=lambda: ["~/.root-agent/commands", "./.root-agent/commands"])
    allow_local_commands: bool = True


class RootAgentConfig(BaseModel):
    schema_version: Literal[1] = 1
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    commands: CommandsConfig = Field(default_factory=CommandsConfig)


def load_config(path: str | Path | None = None) -> RootAgentConfig:
    """Load ``root_agent.yaml``; return defaults if the file is absent."""
    if path is None:
        path = Path(__file__).resolve().parents[1] / "config" / "root_agent.yaml"
    path = Path(path)
    if not path.exists():
        return RootAgentConfig()
    data = yaml.safe_load(path.read_text()) or {}
    return RootAgentConfig.model_validate(data)
