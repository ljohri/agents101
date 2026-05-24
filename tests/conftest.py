"""Shared test fixtures.

REPO_ROOT points at the repo root so tests can load registry files via
load_all() — private agents.yaml / workflows.yaml / mcp_servers.yaml when
present, otherwise the committed *.yaml.example samples.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
