"""Load command recipes from disk and report availability."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from root_agent.catalog import CapabilityEntry
from root_agent.commands.schema import CommandSpec
from root_agent.settings import expand_path


class CommandRegistry:
    def __init__(self, dirs: list[str], *, allow_local_commands: bool = True) -> None:
        self.dirs = [Path(expand_path(d) or d) for d in dirs]
        self.allow_local_commands = allow_local_commands
        self._specs: dict[str, CommandSpec] = {}

    def load(self) -> None:
        """(Re)load all ``*.yaml`` recipes from the configured directories."""
        specs: dict[str, CommandSpec] = {}
        for directory in self.dirs:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.yaml")):
                data = yaml.safe_load(path.read_text()) or {}
                spec = CommandSpec.model_validate(data)
                specs[spec.name] = spec  # later dirs override earlier (local > global)
        self._specs = specs

    def specs(self) -> list[CommandSpec]:
        return list(self._specs.values())

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    @staticmethod
    def _missing_binaries(spec: CommandSpec) -> list[str]:
        return [binary for binary in spec.requires if shutil.which(binary) is None]

    def is_available(self, spec: CommandSpec) -> bool:
        return self.allow_local_commands and not self._missing_binaries(spec)

    def availability(self) -> list[dict]:
        """Per-command availability for ``GET /commands`` and the CLI."""
        rows: list[dict] = []
        for spec in self.specs():
            missing = self._missing_binaries(spec)
            rows.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "available": self.allow_local_commands and not missing,
                    "missing_binaries": missing,
                    "disabled": not self.allow_local_commands,
                }
            )
        return rows

    def capability_entries(self) -> list[CapabilityEntry]:
        """Expose only currently-available commands to the planner."""
        entries: list[CapabilityEntry] = []
        for spec in self.specs():
            if not self.is_available(spec):
                continue
            entries.append(
                CapabilityEntry(
                    uri=spec.capability_uri(),
                    kind="command",
                    description=spec.when_to_use or spec.description,
                )
            )
        return entries
