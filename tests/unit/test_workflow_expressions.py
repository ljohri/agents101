"""Workflow expression tests."""

from __future__ import annotations

from agent_stack.runtime.workflows.expressions import render_template, render_value


def test_len_expression() -> None:
    scope = {"inputs": {"xs": [1, 2, 3]}}
    assert render_template("{{ len(inputs.xs) }}", scope) == 3


def test_nested_render() -> None:
    scope = {"inputs": {"pdf_path": "/tmp/x.pdf"}, "steps": {"a": {"refs": [1]}}}
    out = render_value({"path": "{{ inputs.pdf_path }}", "n": "{{ len(steps.a.refs) }}"}, scope)
    assert out["path"] == "/tmp/x.pdf"
    assert out["n"] == 1
