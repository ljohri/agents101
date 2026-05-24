"""Registry loader.

Loads and cross-validates agents.yaml, workflows.yaml, and mcp_servers.yaml.
Contracts pinned in:
- docs/architecture/01-config-and-registries.md sec 4 (loader precedence)
- docs/architecture/03-workflows.md (workflow grammar)
- docs/architecture/04-mcp-integration.md (mcp registry)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .schemas import (
    AgentsYaml,
    McpServersYaml,
    StepCall,
    StepParallel,
    WorkflowsYaml,
)

DEFAULT_AGENTS_FILE = "agents.yaml"
DEFAULT_WORKFLOWS_FILE = "workflows.yaml"
DEFAULT_MCP_SERVERS_FILE = "mcp_servers.yaml"


class ConfigError(Exception):
    """Raised on schema or cross-validation failures."""


@dataclass(frozen=True)
class LoadedConfig:
    agents: AgentsYaml
    workflows: WorkflowsYaml
    mcp_servers: McpServersYaml
    root: Path


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"{path.name} not found at {path}")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: top-level must be a mapping")
    return data


def _parse(model: type, data: dict[str, Any], name: str):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{name}: {exc}") from exc


# Capability URI grammar (per docs/architecture/02-capabilities.md sec 3.1)
_IDENT = r"[A-Za-z][A-Za-z0-9_-]*"
_URI_RE = re.compile(
    rf"^(?:"
    rf"mcp\.(?P<mcp_server>{_IDENT})\.(?P<mcp_tool>(?:resource:.+|prompt:{_IDENT}|{_IDENT}))"
    rf"|agent\.(?P<agent_id>{_IDENT})\.(?P<skill_id>{_IDENT})"
    rf"|workflow\.(?P<workflow_id>{_IDENT})"
    rf"|builtin\.(?P<builtin_name>{_IDENT})"
    rf")$"
)


def _parse_uri(uri: str) -> tuple[str, dict[str, str]]:
    m = _URI_RE.match(uri)
    if not m:
        raise ConfigError(f"invalid capability URI {uri!r}")
    parts = {k: v for k, v in m.groupdict().items() if v is not None}
    if "mcp_server" in parts:
        return "mcp", parts
    if "agent_id" in parts:
        return "agent", parts
    if "workflow_id" in parts:
        return "workflow", parts
    return "builtin", parts


def _cross_validate(loaded: LoadedConfig) -> None:
    """Apply the cross-file rules from 01-config-and-registries.md sec 4."""
    agent_skills: dict[str, set[str]] = {
        a.id: {s.id for s in a.skills} for a in loaded.agents.agents.values()
    }
    workflow_ids = set(loaded.workflows.workflows.keys())

    def _check_call_uri(workflow_id: str, step_id: str, uri: str) -> None:
        scheme, parts = _parse_uri(uri)
        if scheme == "agent":
            aid = parts["agent_id"]
            sid = parts["skill_id"]
            if aid not in agent_skills:
                raise ConfigError(
                    f"workflow {workflow_id!r} step {step_id!r}: "
                    f"unknown agent {aid!r} in {uri!r}"
                )
            if sid not in agent_skills[aid]:
                raise ConfigError(
                    f"workflow {workflow_id!r} step {step_id!r}: "
                    f"agent {aid!r} has no skill {sid!r} (uri={uri!r})"
                )
        elif scheme == "workflow":
            target = parts["workflow_id"]
            if target == workflow_id:
                raise ConfigError(
                    f"workflow {workflow_id!r} step {step_id!r}: "
                    f"self-call via workflow.{target} is not allowed in v0.1"
                )
            if target not in workflow_ids:
                raise ConfigError(
                    f"workflow {workflow_id!r} step {step_id!r}: "
                    f"unknown sub-workflow {target!r}"
                )
        # scheme == 'mcp': validity is checked at runtime when the bridge connects.
        # scheme == 'builtin': always valid (closed set is enforced by step kinds).

    for wf_id, wf in loaded.workflows.workflows.items():
        step_ids = {s.id for s in wf.steps}
        for step in wf.steps:
            if isinstance(step, StepCall):
                _check_call_uri(wf_id, step.id, step.call)
            elif isinstance(step, StepParallel):
                if step.call is not None:
                    _check_call_uri(wf_id, step.id, step.call)
                if step.branches is not None:
                    for branch in step.branches:
                        if "call" in branch:
                            _check_call_uri(wf_id, step.id, branch["call"])

        # branch.goto targets must be known step ids in the same workflow
        for step in wf.steps:
            if step.on_error and step.on_error.action == "goto":
                target = step.on_error.goto
                if target not in step_ids:
                    raise ConfigError(
                        f"workflow {wf_id!r} step {step.id!r}: "
                        f"on_error.goto={target!r} is not a step in this workflow"
                    )


def load_all(root: str | Path = ".") -> LoadedConfig:
    """Load and cross-validate all three registry files from `root`."""
    root_path = Path(root).resolve()

    agents_raw = _read_yaml(root_path / DEFAULT_AGENTS_FILE)
    workflows_raw = _read_yaml(root_path / DEFAULT_WORKFLOWS_FILE)
    mcp_raw = _read_yaml(root_path / DEFAULT_MCP_SERVERS_FILE)

    # Friendlier message than the Pydantic discriminator error for schema_version.
    for name, raw in (
        (DEFAULT_AGENTS_FILE, agents_raw),
        (DEFAULT_WORKFLOWS_FILE, workflows_raw),
        (DEFAULT_MCP_SERVERS_FILE, mcp_raw),
    ):
        sv = raw.get("schema_version")
        if sv != 1:
            raise ConfigError(
                f"{name}: unknown schema_version {sv!r}; "
                f"see docs/architecture/01-config-and-registries.md sec 7 (migrations)"
            )

    agents = _parse(AgentsYaml, agents_raw, DEFAULT_AGENTS_FILE)
    workflows = _parse(WorkflowsYaml, workflows_raw, DEFAULT_WORKFLOWS_FILE)
    mcp_servers = _parse(McpServersYaml, mcp_raw, DEFAULT_MCP_SERVERS_FILE)

    loaded = LoadedConfig(
        agents=agents,
        workflows=workflows,
        mcp_servers=mcp_servers,
        root=root_path,
    )
    _cross_validate(loaded)
    return loaded
