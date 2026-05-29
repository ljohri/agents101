import asyncio

from root_agent.commands.exec import CommandExecutor
from root_agent.commands.registry import CommandRegistry

ECHO_RECIPE = """
name: say
description: echo a message
when_to_use: emit text
requires: [echo]
params:
  - name: msg
    type: string
    required: true
argv_template: ["echo", "{msg}"]
"""

DENY_RECIPE = """
name: say
requires: [echo]
params:
  - name: msg
    type: string
    required: true
argv_template: ["echo", "{msg}"]
safety:
  deny_patterns: ["secret"]
"""


def _registry(tmp_path, recipe=ECHO_RECIPE):
    (tmp_path / "say.yaml").write_text(recipe)
    reg = CommandRegistry([str(tmp_path)])
    reg.load()
    return reg


def test_registry_loads_and_reports_availability(tmp_path):
    reg = _registry(tmp_path)
    assert reg.get("say") is not None
    avail = {r["name"]: r for r in reg.availability()}
    assert avail["say"]["available"] is True
    assert any(c.uri == "command.say" for c in reg.capability_entries())


def test_exec_runs_argv(tmp_path):
    ex = CommandExecutor(_registry(tmp_path))
    res = asyncio.run(ex.run("say", {"msg": "hi there"}))
    assert res.ok and "hi there" in res.stdout


def test_exec_missing_required_param(tmp_path):
    ex = CommandExecutor(_registry(tmp_path))
    res = asyncio.run(ex.run("say", {}))
    assert not res.ok and "missing required param" in res.error


def test_exec_unknown_param_rejected(tmp_path):
    ex = CommandExecutor(_registry(tmp_path))
    res = asyncio.run(ex.run("say", {"msg": "x", "bogus": 1}))
    assert not res.ok and "unknown params" in res.error


def test_exec_deny_pattern_blocks(tmp_path):
    ex = CommandExecutor(_registry(tmp_path, DENY_RECIPE))
    res = asyncio.run(ex.run("say", {"msg": "my secret value"}))
    assert not res.ok and "deny pattern" in res.error


def test_exec_disabled(tmp_path):
    ex = CommandExecutor(_registry(tmp_path), allow_local_commands=False)
    res = asyncio.run(ex.run("say", {"msg": "x"}))
    assert not res.ok and "disabled" in res.error


def test_exec_unknown_command(tmp_path):
    ex = CommandExecutor(_registry(tmp_path))
    res = asyncio.run(ex.run("nope", {}))
    assert not res.ok and "unknown command" in res.error
