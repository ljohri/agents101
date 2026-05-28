"""Structured logging + simple metrics."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from typing import Any

from agent_stack.runtime.otel import current_trace_ids
from agent_stack.runtime.otel import start_span as otel_start_span

logger = logging.getLogger("agent_stack.observability")

_metrics: dict[str, float] = defaultdict(float)


def log_event(msg: str, **fields: Any) -> None:
    trace_id, span_id = current_trace_ids()
    payload = {"msg": msg, **fields}
    if trace_id:
        payload["trace_id"] = trace_id
    if span_id:
        payload["span_id"] = span_id
    logger.info(json.dumps(payload, default=str))


def inc(name: str, labels: dict[str, str] | None = None, amount: float = 1) -> None:
    key = name if not labels else name + "|" + "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    _metrics[key] += amount


def render_metrics() -> str:
    lines = []
    for key, val in sorted(_metrics.items()):
        lines.append(f"# TYPE {key.split('|')[0]} counter")
        lines.append(f"{key} {val}")
    return "\n".join(lines) + "\n"


class Span:
    def __init__(self, name: str, **attrs: Any) -> None:
        self.name = name
        self.attrs = attrs
        self._start = time.perf_counter()

    def __enter__(self):
        self._cm = otel_start_span(self.name, **self.attrs)
        self._span = self._cm.__enter__()
        log_event(f"{self.name}.started", **self.attrs)
        return self

    def __exit__(self, exc_type, exc, tb):
        if hasattr(self, "_cm"):
            self._cm.__exit__(exc_type, exc, tb)
        dur = int((time.perf_counter() - self._start) * 1000)
        log_event(f"{self.name}.completed", duration_ms=dur, ok=exc is None, **self.attrs)
