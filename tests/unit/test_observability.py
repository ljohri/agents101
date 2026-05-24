"""Observability unit tests."""

from __future__ import annotations

from agent_stack.runtime.observability import Span, inc, render_metrics


def test_metrics_increment() -> None:
    inc("capability_invocations_total", {"uri": "agent.generic.echo", "ok": "true"})
    body = render_metrics()
    assert "capability_invocations_total" in body


def test_span_context() -> None:
    with Span("capability.invoked", uri="agent.generic.echo"):
        pass
