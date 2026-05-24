"""Golden tests for artifact generation (uses .example configs via loader fallback)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_stack.registry.agent_card import build_agent_card
from agent_stack.registry.config import load_all
from agent_stack.registry.instructions import build_agents_md
from tests.conftest import REPO_ROOT


def test_generate_card_shape() -> None:
    config = load_all(REPO_ROOT)
    card = build_agent_card(config)
    assert card["name"]
    assert card["skills"]
    assert "authentication" in card
    # round-trip JSON
    json.dumps(card)


def test_generate_agents_md_contains_agents() -> None:
    config = load_all(REPO_ROOT)
    md = build_agents_md(config)
    assert "local-bibliography-agent" in md
    assert "bibliography-research" in md


def test_generate_script_writes_private_outputs(tmp_path: Path) -> None:
    import subprocess
    import sys

    for name in ("agents.yaml", "workflows.yaml", "mcp_servers.yaml"):
        src = REPO_ROOT / f"{name}.example"
        if src.exists():
            (tmp_path / name).write_text(src.read_text())
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_agent_artifacts.py"), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".well-known" / "agent-card.json").exists()
