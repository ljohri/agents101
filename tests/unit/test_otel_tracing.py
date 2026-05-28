"""OTEL tracing unit tests."""

from __future__ import annotations

import pytest

from agent_stack.runtime.capabilities import CapabilityCall, CapabilityRegistry, InvocationContext
from agent_stack.runtime.otel import current_trace_ids, inject_trace_headers, start_span
from agent_stack.runtime.workflows.executor import WorkflowExecutor
from tests.conftest import REPO_ROOT


def test_start_span_noop_without_otel() -> None:
    with start_span("capability.invoked"):
        trace_id, span_id = current_trace_ids()
        # In non-OTEL mode this is empty; in OTEL mode it is populated.
        assert isinstance(trace_id, str)
        assert isinstance(span_id, str)


def test_inject_trace_headers_no_crash() -> None:
    headers: dict[str, str] = {}
    inject_trace_headers(headers)
    assert isinstance(headers, dict)


@pytest.mark.asyncio
async def test_capability_invoke_sets_trace_fields() -> None:
    cfg = __import__("agent_stack.registry.config", fromlist=["load_all"]).load_all(str(REPO_ROOT))
    reg = CapabilityRegistry(cfg)
    ctx = InvocationContext(conversation_id="conv-1")

    async def agent_handler(agent_id, skill_id, inputs, _ctx):  # noqa: ANN001
        return {"agent_id": agent_id, "skill_id": skill_id, "inputs": inputs}

    res = await reg.invoke(
        CapabilityCall(uri="agent.generic.echo", inputs={"message": "hi"}),
        ctx,
        agent_handler=agent_handler,
    )
    assert res.ok
    assert isinstance(res.trace_id, str) and len(res.trace_id) > 0
    assert isinstance(res.span_id, str) and len(res.span_id) > 0


@pytest.mark.asyncio
async def test_workflow_executor_propagates_workflow_context() -> None:
    cfg = __import__("agent_stack.registry.config", fromlist=["load_all"]).load_all(str(REPO_ROOT))
    reg = CapabilityRegistry(cfg)
    executor = WorkflowExecutor(cfg, reg)
    seen: list[InvocationContext] = []

    async def invoke_fn(call, inner_ctx):  # noqa: ANN001
        seen.append(inner_ctx)
        from agent_stack.runtime.capabilities import CapabilityResult

        output = {"ok": True}
        if call.uri.endswith("extract-bibliography"):
            output = [{"id": "r1", "title": "Paper"}]
        elif call.uri.endswith("resolve-open-access-pdfs"):
            output = [{"id": "oa-1", "pdf_url": "https://example.org/oa-1.pdf"}]
        elif call.uri.endswith("download_url"):
            output = {"saved": True}
        return CapabilityResult(
            uri=call.uri,
            ok=True,
            output=output,
            trace_id=inner_ctx.trace_id,
            span_id="x",
        )

    ctx = InvocationContext(conversation_id="conv-2", trace_id="0123456789abcdef0123456789abcdef")
    await executor.run(
        "bibliography_research",
        {"pdf_path": "./data/paper.pdf"},
        ctx,
        invoke_fn,
    )
    assert any(s.workflow_id == "bibliography_research" for s in seen)
    assert all(s.workflow_version for s in seen)
    assert any(s.step_id == "extract" for s in seen)
