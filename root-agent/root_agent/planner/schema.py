"""Structured outputs for the judge and planner."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class JudgeDecision(BaseModel):
    """Result of LLM-as-judge."""

    decision: Literal["use_workflow", "plan"]
    # Set only when decision == use_workflow; must be an exposed workflow skill id.
    workflow_id: str | None = None
    reason: str = ""


class PlanStep(BaseModel):
    """One step of a synthesized plan."""

    id: str
    # Capability URI: agent.<id>.<skill> | mcp.<server>.<tool> | command.<name>
    call: str
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    # Optional name to store this step's output under for later steps.
    output: str | None = None

    model_config = {"populate_by_name": True}


class Plan(BaseModel):
    """An ordered, capability-constrained plan synthesized by the planner."""

    rationale: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    # Optional final shaping of the result, referencing step outputs.
    output: dict[str, str] = Field(default_factory=dict)
