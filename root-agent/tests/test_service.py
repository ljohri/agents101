import asyncio

from root_agent.config import RootAgentConfig
from root_agent.discovery import AgentInfo
from root_agent.llm.base import FakeLLMClient
from root_agent.planner.executor import ExecutionResult
from root_agent.service import RootAgentService
from root_agent.settings import Settings


class StubExecutor:
    def __init__(self):
        self.called = None

    async def run_workflow(self, workflow_id, inputs, memory, **kwargs):
        self.called = ("workflow", workflow_id)
        return ExecutionResult(ok=True, mode="workflow", detail=workflow_id)

    async def run_plan(self, plan, inputs, memory, **kwargs):
        self.called = ("plan", plan)
        return ExecutionResult(ok=True, mode="plan", detail=plan.rationale)


def _service(tmp_path, llm):
    settings = Settings(
        global_memory_path=str(tmp_path / "G.md"),
        local_memory_path=str(tmp_path / "L.md"),
    )
    return RootAgentService(settings, RootAgentConfig(), llm=llm)


def _seed_workflow(svc, skill_id="wf1"):
    svc.discovery._agents = {
        "workflows": AgentInfo(
            id="workflows",
            name="wf",
            url="http://x/a2a/workflows",
            endpoint="/a2a/workflows",
            skills=[{"id": skill_id, "description": "d"}],
            is_workflows=True,
            status="up",
        )
    }


def test_handle_request_routes_to_workflow(tmp_path):
    llm = FakeLLMClient('{"decision":"use_workflow","workflow_id":"wf1","reason":"r"}')
    svc = _service(tmp_path, llm)
    _seed_workflow(svc)
    svc.executor = StubExecutor()
    out = asyncio.run(svc.handle_request("run wf1", {}, "c1"))
    assert out["ok"] and out["mode"] == "workflow" and out["workflow_id"] == "wf1"
    # The request is recorded into session memory.
    assert "wf1" in "".join(svc.memory_store._sessions["c1"]) or svc.memory_store.session("c1")


def test_handle_request_routes_to_plan(tmp_path):
    # Judge says plan, then planner returns a one-step plan over a known capability.
    llm = FakeLLMClient(
        [
            '{"decision":"plan","reason":"none fit"}',
            '{"rationale":"r","steps":[{"id":"s1","call":"command.x"}]}',
        ]
    )
    svc = _service(tmp_path, llm)
    _seed_workflow(svc)
    # Make command.x a known capability so the planner validation passes.
    svc.command_registry._specs = {}
    from root_agent.commands.schema import CommandSpec

    svc.command_registry._specs = {"x": CommandSpec(name="x", argv_template=["echo"])}
    stub = StubExecutor()
    svc.executor = stub
    out = asyncio.run(svc.handle_request("do something custom", {}, "c2"))
    assert out["ok"] and out["mode"] == "plan"
    assert stub.called[0] == "plan"


def test_handle_request_without_llm(tmp_path):
    svc = _service(tmp_path, None)
    svc.llm_error = "no provider"
    out = asyncio.run(svc.handle_request("anything"))
    assert not out["ok"] and "LLM not configured" in out["error"]
