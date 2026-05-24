"""Schema + cross-validation tests for workflows.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_stack.registry.config import ConfigError, load_all
from agent_stack.registry.schemas import (
    StepCall,
    StepHumanApproval,
    StepParallel,
)


def test_loads_repo_workflows_yaml(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    assert "bibliography_research" in cfg.workflows.workflows
    wf = cfg.workflows.workflows["bibliography_research"]
    assert wf.version == "0.1.0"
    assert wf.exposed_as_skill is not None
    assert wf.exposed_as_skill.id == "bibliography-research"
    kinds = {type(step).__name__ for step in wf.steps}
    assert {"StepCall", "StepHumanApproval", "StepParallel"} <= kinds


def test_step_types_resolved_correctly(repo_root: Path) -> None:
    cfg = load_all(repo_root)
    wf = cfg.workflows.workflows["bibliography_research"]
    by_id = {s.id: s for s in wf.steps}
    assert isinstance(by_id["extract"], StepCall)
    assert isinstance(by_id["resolve"], StepCall)
    assert isinstance(by_id["approve"], StepHumanApproval)
    assert isinstance(by_id["download"], StepParallel)
    assert by_id["download"].for_each is not None
    assert by_id["download"].as_ == "candidate"


def test_rejects_unknown_agent_skill_reference(tmp_path: Path) -> None:
    _seed(tmp_path, workflows="""
schema_version: 1
workflows:
  bad:
    version: 0.1.0
    name: Bad
    steps:
      - id: only
        call: agent.does_not_exist.nope
""".strip())
    with pytest.raises(ConfigError, match="unknown agent"):
        load_all(tmp_path)


def test_rejects_unknown_sub_workflow(tmp_path: Path) -> None:
    _seed(tmp_path, workflows="""
schema_version: 1
workflows:
  bad:
    version: 0.1.0
    name: Bad
    steps:
      - id: only
        call: workflow.does_not_exist
""".strip())
    with pytest.raises(ConfigError, match="unknown sub-workflow"):
        load_all(tmp_path)


def test_rejects_invalid_capability_uri(tmp_path: Path) -> None:
    _seed(tmp_path, workflows="""
schema_version: 1
workflows:
  bad:
    version: 0.1.0
    name: Bad
    steps:
      - id: only
        call: not-a-valid-uri
""".strip())
    with pytest.raises(ConfigError, match="invalid capability URI"):
        load_all(tmp_path)


def test_rejects_duplicate_step_ids(tmp_path: Path) -> None:
    _seed(tmp_path, workflows="""
schema_version: 1
workflows:
  bad:
    version: 0.1.0
    name: Bad
    steps:
      - id: dup
        call: builtin.assign
      - id: dup
        call: builtin.assign
""".strip())
    with pytest.raises(ConfigError, match="duplicate step id"):
        load_all(tmp_path)


def test_rejects_parallel_with_both_branches_and_for_each(tmp_path: Path) -> None:
    _seed(tmp_path, workflows="""
schema_version: 1
workflows:
  bad:
    version: 0.1.0
    name: Bad
    steps:
      - id: only
        type: parallel
        branches: [{ id: x, call: builtin.assign }]
        for_each: "{{ inputs.xs }}"
        as: item
        call: builtin.assign
""".strip())
    with pytest.raises(ConfigError, match="exactly one of"):
        load_all(tmp_path)


def _seed(tmp_path: Path, *, workflows: str) -> None:
    (tmp_path / "agents.yaml").write_text(
        "schema_version: 1\nruntime: {}\nagents: {}\n"
    )
    (tmp_path / "mcp_servers.yaml").write_text(
        "schema_version: 1\nservers: {}\n"
    )
    (tmp_path / "workflows.yaml").write_text(workflows)
