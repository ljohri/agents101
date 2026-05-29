import asyncio

from root_agent.a2a_client import A2AClient, A2AResult
from root_agent.commands.exec import CommandExecutor
from root_agent.commands.registry import CommandRegistry
from root_agent.memory.schema import MemoryContext
from root_agent.planner.executor import Executor, render
from root_agent.planner.schema import Plan, PlanStep

MEM = MemoryContext(merged="## Global\n- pref")


class FakeClient(A2AClient):
    def __init__(self):
        super().__init__("http://x")
        self.sent = []

    async def message_send(
        self, endpoint, *, skill=None, inputs=None, conversation_id=None, metadata=None, trace_id=None
    ):
        self.sent.append({"endpoint": endpoint, "skill": skill, "inputs": inputs, "metadata": metadata})
        return A2AResult(ok=True, content={"echo": inputs, "skill": skill})


def test_render_preserves_type_and_substitutes():
    ctx = {"inputs": {"p": "./data"}, "steps": {"s1": {"refs": [1, 2, 3]}}, "memory": "m"}
    assert render("{{ steps.s1.refs }}", ctx) == [1, 2, 3]
    assert render("path={{ inputs.p }}", ctx) == "path=./data"


def test_run_workflow_passes_memory_metadata():
    fc = FakeClient()
    ex = Executor(fc, workflows_endpoint="/a2a/workflows")
    res = asyncio.run(ex.run_workflow("wf1", {"a": 1}, MEM, conversation_id="c1"))
    assert res.ok and res.mode == "workflow"
    assert fc.sent[-1]["endpoint"] == "/a2a/workflows"
    assert "memory_context" in fc.sent[-1]["metadata"]


def test_run_plan_agent_step_with_templating():
    fc = FakeClient()
    ex = Executor(fc)
    plan = Plan(
        rationale="r",
        steps=[PlanStep(id="s1", call="agent.bibliography.extract", **{"with": {"input": "{{ inputs.pdf }}"}})],
    )
    res = asyncio.run(ex.run_plan(plan, {"pdf": "x.pdf"}, MEM))
    assert res.ok and res.mode == "plan"
    assert fc.sent[-1]["endpoint"] == "/a2a/bibliography"
    assert fc.sent[-1]["inputs"] == {"input": "x.pdf"}


def test_run_plan_command_step(tmp_path):
    recipe = (
        "name: say\n"
        "requires: [echo]\n"
        "params:\n"
        "  - name: msg\n"
        "    required: true\n"
        'argv_template: ["echo", "{msg}"]\n'
    )
    (tmp_path / "say.yaml").write_text(recipe)
    reg = CommandRegistry([str(tmp_path)])
    reg.load()
    ex = Executor(FakeClient(), command_executor=CommandExecutor(reg))
    plan = Plan(steps=[PlanStep(id="s1", call="command.say", **{"with": {"msg": "hello"}})])
    res = asyncio.run(ex.run_plan(plan, {}, MEM))
    assert res.ok
    assert "hello" in res.steps[0].output


def test_run_plan_stops_on_failure():
    fc = FakeClient()
    ex = Executor(fc)  # no command executor configured
    plan = Plan(steps=[PlanStep(id="s1", call="command.missing", **{"with": {}})])
    res = asyncio.run(ex.run_plan(plan, {}, MEM))
    assert not res.ok and "step 's1' failed" in res.error
