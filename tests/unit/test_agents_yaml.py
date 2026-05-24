"""Schema + cross-validation tests for agents.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_stack.registry.config import ConfigError, load_all
from agent_stack.registry.schemas import (
    AgentRuntimeLocal,
    AgentRuntimeRemote,
    AgentsYaml,
)


def test_loads_repo_agents_yaml(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    assert isinstance(cfg.agents, AgentsYaml)
    assert {"generic", "bibliography", "external_researcher"} <= set(cfg.agents.agents)


def test_local_and_remote_discriminator(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    assert isinstance(cfg.agents.agents["generic"].runtime, AgentRuntimeLocal)
    assert isinstance(cfg.agents.agents["bibliography"].runtime, AgentRuntimeLocal)
    assert isinstance(cfg.agents.agents["external_researcher"].runtime, AgentRuntimeRemote)


def test_remote_resilience_defaults_filled(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    rt = cfg.agents.agents["external_researcher"].runtime
    assert isinstance(rt, AgentRuntimeRemote)
    cb = rt.remote.resilience.circuit_breaker
    assert cb.failure_threshold == 5
    assert cb.reset_seconds == 30


def test_rejects_unknown_schema_version(tmp_path: Path) -> None:
    (tmp_path / "agents.yaml").write_text("schema_version: 99\nruntime: {}\nagents: {}\n")
    (tmp_path / "workflows.yaml").write_text("schema_version: 1\nworkflows: {}\n")
    (tmp_path / "mcp_servers.yaml").write_text("schema_version: 1\nservers: {}\n")
    with pytest.raises(ConfigError, match="schema_version"):
        load_all(tmp_path)


def test_rejects_endpoint_collision(tmp_path: Path) -> None:
    (tmp_path / "agents.yaml").write_text(
        """
schema_version: 1
runtime:
  default_base_url: http://127.0.0.1:8080
agents:
  a:
    id: a
    name: a
    version: 0.1.0
    description: a
    runtime: { kind: local, module: x, factory: y }
    server: { base_url: http://127.0.0.1:8080, a2a_endpoint: /a2a/shared }
    skills:
      - { id: s, name: s, description: s }
  b:
    id: b
    name: b
    version: 0.1.0
    description: b
    runtime: { kind: local, module: x, factory: y }
    server: { base_url: http://127.0.0.1:8080, a2a_endpoint: /a2a/shared }
    skills:
      - { id: s, name: s, description: s }
""".strip()
    )
    (tmp_path / "workflows.yaml").write_text("schema_version: 1\nworkflows: {}\n")
    (tmp_path / "mcp_servers.yaml").write_text("schema_version: 1\nservers: {}\n")
    with pytest.raises(ConfigError, match="collides"):
        load_all(tmp_path)


def test_rejects_id_mismatch(tmp_path: Path) -> None:
    (tmp_path / "agents.yaml").write_text(
        """
schema_version: 1
runtime:
  default_base_url: http://127.0.0.1:8080
agents:
  a:
    id: WRONG
    name: a
    version: 0.1.0
    description: a
    runtime: { kind: local, module: x, factory: y }
    skills:
      - { id: s, name: s, description: s }
""".strip()
    )
    (tmp_path / "workflows.yaml").write_text("schema_version: 1\nworkflows: {}\n")
    (tmp_path / "mcp_servers.yaml").write_text("schema_version: 1\nservers: {}\n")
    with pytest.raises(ConfigError, match="must equal the map key"):
        load_all(tmp_path)
