"""Secret leak guard for committed sample configs."""

from __future__ import annotations

import re

import yaml

from tests.conftest import REPO_ROOT

SECRET_KEYS = re.compile(
    r"(token|secret|password|api_key|private_key|refresh_token|client_secret|service_account|bearer|credentials)",
    re.I,
)


def _check_obj(obj, path="") -> list[str]:
    issues: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SECRET_KEYS.search(str(k)) and not str(k).endswith("_env") and "env_" not in str(k):
                issues.append(f"{path}.{k}")
            issues.extend(_check_obj(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            issues.extend(_check_obj(v, f"{path}[{i}]"))
    return issues


def test_example_yamls_have_no_secret_values() -> None:
    for name in ("agents.yaml.example", "workflows.yaml.example", "mcp_servers.yaml.example"):
        path = REPO_ROOT / name
        data = yaml.safe_load(path.read_text())
        issues = _check_obj(data, name)
        assert not issues, f"secret-looking keys in {name}: {issues}"
