import asyncio

import pytest

from root_agent.catalog import CapabilityEntry, Catalog, WorkflowEntry
from root_agent.llm.base import FakeLLMClient
from root_agent.memory.schema import MemoryContext
from root_agent.planner.judge import Judge
from root_agent.planner.planner import Planner, PlannerError

CATALOG = Catalog(
    workflows=[WorkflowEntry(skill_id="bibliography-research", name="Bib", description="extract+resolve")],
    capabilities=[
        CapabilityEntry(uri="agent.bibliography.extract", kind="agent"),
        CapabilityEntry(uri="command.ripgrep-search", kind="command"),
    ],
)
MEM = MemoryContext(merged="## Global\n- prefer arxiv")


def test_judge_picks_existing_workflow():
    judge = Judge(FakeLLMClient('{"decision":"use_workflow","workflow_id":"bibliography-research","reason":"fits"}'))
    decision = asyncio.run(judge.decide("find pdfs", CATALOG, MEM))
    assert decision.decision == "use_workflow"
    assert decision.workflow_id == "bibliography-research"


def test_judge_downgrades_unknown_workflow_to_plan():
    judge = Judge(FakeLLMClient('{"decision":"use_workflow","workflow_id":"ghost","reason":"x"}'))
    decision = asyncio.run(judge.decide("x", CATALOG, MEM))
    assert decision.decision == "plan"


def test_planner_returns_valid_plan():
    planner = Planner(
        FakeLLMClient('{"rationale":"r","steps":[{"id":"s1","call":"agent.bibliography.extract","with":{"x":1}}]}')
    )
    plan = asyncio.run(planner.plan("x", CATALOG, MEM))
    assert plan.steps[0].call == "agent.bibliography.extract"
    assert plan.steps[0].with_ == {"x": 1}


def test_planner_rejects_unknown_capability():
    planner = Planner(FakeLLMClient('{"steps":[{"id":"s1","call":"agent.unknown.skill"}]}'))
    with pytest.raises(PlannerError):
        asyncio.run(planner.plan("x", CATALOG, MEM))


def test_planner_rejects_empty_plan():
    planner = Planner(FakeLLMClient('{"steps":[]}'))
    with pytest.raises(PlannerError):
        asyncio.run(planner.plan("x", CATALOG, MEM))
