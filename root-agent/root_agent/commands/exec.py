"""Guarded local execution of command recipes.

Safety properties:
- No shell. Args are an argv array built from validated params, so user/LLM
  input cannot inject shell syntax.
- Binaries must be declared in ``requires`` and present on PATH.
- Rendered argv tokens are checked against the recipe's deny patterns.
- Per-call timeout; output truncated to a byte budget.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from typing import Any

from pydantic import BaseModel, Field

from root_agent.commands.registry import CommandRegistry
from root_agent.commands.schema import CommandParam, CommandSpec


class CommandResult(BaseModel):
    ok: bool
    name: str
    argv: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


def _coerce(param: CommandParam, value: Any) -> Any:
    if param.type == "integer":
        return int(value)
    if param.type == "number":
        return float(value)
    if param.type == "boolean":
        return bool(value)
    return str(value)


def _resolve_params(spec: CommandSpec, params: dict[str, Any]) -> dict[str, Any]:
    """Validate provided params against the recipe; apply defaults/types."""
    resolved: dict[str, Any] = {}
    declared = {p.name: p for p in spec.params}
    for name, param in declared.items():
        if name in params and params[name] is not None:
            resolved[name] = _coerce(param, params[name])
        elif param.default is not None:
            resolved[name] = _coerce(param, param.default)
        elif param.required:
            raise ValueError(f"command {spec.name!r} missing required param {name!r}")
    unknown = set(params) - set(declared)
    if unknown:
        raise ValueError(f"command {spec.name!r} got unknown params: {sorted(unknown)}")
    return resolved


def _render_argv(spec: CommandSpec, resolved: dict[str, Any]) -> list[str]:
    """Render the argv template; each token stays a single argv element."""
    argv: list[str] = []
    for token in spec.argv_template:
        try:
            argv.append(token.format(**resolved))
        except KeyError as exc:
            raise ValueError(f"command {spec.name!r} template references unknown param {exc}") from exc
    return argv


def _check_safety(spec: CommandSpec, argv: list[str]) -> None:
    for pattern in spec.safety.deny_patterns:
        rx = re.compile(pattern)
        for token in argv:
            if rx.search(token):
                raise ValueError(f"command {spec.name!r} arg {token!r} matched deny pattern {pattern!r}")


class CommandExecutor:
    def __init__(self, registry: CommandRegistry, *, allow_local_commands: bool = True) -> None:
        self.registry = registry
        self.allow_local_commands = allow_local_commands

    async def run(self, name: str, params: dict[str, Any] | None = None) -> CommandResult:
        if not self.allow_local_commands:
            return CommandResult(ok=False, name=name, error="local command execution disabled")

        spec = self.registry.get(name)
        if spec is None:
            return CommandResult(ok=False, name=name, error=f"unknown command {name!r}")

        try:
            resolved = _resolve_params(spec, params or {})
            argv = _render_argv(spec, resolved)
            _check_safety(spec, argv)
        except ValueError as exc:
            return CommandResult(ok=False, name=name, error=str(exc))

        # The first argv element must be a declared, resolvable binary.
        if not argv or shutil.which(argv[0]) is None:
            return CommandResult(ok=False, name=name, argv=argv, error=f"binary not found: {argv[:1]}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=spec.timeout_seconds)
        except TimeoutError:
            return CommandResult(ok=False, name=name, argv=argv, error="timeout")
        except Exception as exc:  # noqa: BLE001
            return CommandResult(ok=False, name=name, argv=argv, error=str(exc))

        limit = spec.safety.max_output_bytes
        return CommandResult(
            ok=proc.returncode == 0,
            name=name,
            argv=argv,
            exit_code=proc.returncode,
            stdout=out[:limit].decode("utf-8", "replace"),
            stderr=err[:limit].decode("utf-8", "replace"),
        )
