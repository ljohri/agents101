"""Schema tests for mcp_servers.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_stack.registry.config import ConfigError, load_all
from agent_stack.registry.schemas import McpServer


def test_loads_repo_mcp_servers_yaml(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    assert {"filesystem-safe", "fetch"} <= set(cfg.mcp_servers.servers)
    fs = cfg.mcp_servers.servers["filesystem-safe"]
    assert isinstance(fs, McpServer)
    assert fs.transport == "stdio"
    assert "read_file" in fs.capabilities_filter.allow_tools
    fetch = cfg.mcp_servers.servers["fetch"]
    assert fetch.transport == "http"
    assert fetch.headers_env == {"Authorization": "FETCH_MCP_BEARER"}


def test_rejects_stdio_without_command(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "mcp_servers.yaml").write_text(
        """
schema_version: 1
servers:
  bad:
    id: bad
    transport: stdio
""".strip()
    )
    with pytest.raises(ConfigError, match="requires 'command'"):
        load_all(tmp_path)


def test_rejects_http_without_url(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "mcp_servers.yaml").write_text(
        """
schema_version: 1
servers:
  bad:
    id: bad
    transport: http
""".strip()
    )
    with pytest.raises(ConfigError, match="requires 'url'"):
        load_all(tmp_path)


def test_rejects_stdio_with_url(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "mcp_servers.yaml").write_text(
        """
schema_version: 1
servers:
  bad:
    id: bad
    transport: stdio
    command: foo
    url: http://x
""".strip()
    )
    with pytest.raises(ConfigError, match="must not set 'url'"):
        load_all(tmp_path)


def _seed(tmp_path: Path) -> None:
    (tmp_path / "agents.yaml").write_text(
        "schema_version: 1\nruntime: {}\nagents: {}\n"
    )
    (tmp_path / "workflows.yaml").write_text(
        "schema_version: 1\nworkflows: {}\n"
    )
