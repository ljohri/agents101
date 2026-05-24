"""Shared test fixtures.

REPO_ROOT points at the repo root so tests can load the real registry files
(agents.yaml, workflows.yaml, mcp_servers.yaml) committed alongside the
architecture docs (see docs/build-plan.md sec 9 DoD).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
