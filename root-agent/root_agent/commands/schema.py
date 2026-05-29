"""Command recipe schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandParam(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean"] = "string"
    required: bool = False
    default: Any | None = None
    description: str = ""


class CommandSafety(BaseModel):
    # Regexes; if any matches a rendered argv token, the command is rejected.
    deny_patterns: list[str] = Field(default_factory=list)
    # Truncate captured stdout/stderr to this many bytes.
    max_output_bytes: int = 1_000_000


class CommandSpec(BaseModel):
    name: str
    description: str = ""
    # Free-form guidance the LLM uses to decide when this command applies.
    when_to_use: str = ""
    # Binaries that must exist on PATH for the command to be available.
    requires: list[str] = Field(default_factory=list)
    params: list[CommandParam] = Field(default_factory=list)
    # argv array with {param} placeholders, e.g. ["rg", "--json", "{pattern}", "{path}"].
    argv_template: list[str]
    timeout_seconds: float = 30.0
    safety: CommandSafety = Field(default_factory=CommandSafety)
    output: Literal["raw", "json", "lines"] = "raw"

    def capability_uri(self) -> str:
        return f"command.{self.name}"
