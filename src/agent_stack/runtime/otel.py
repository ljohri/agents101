"""OpenTelemetry setup and helpers."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from agent_stack.settings import Settings

logger = logging.getLogger("agent_stack.otel")

_OTEL_READY = False
_TRACER = None


def setup_otel(settings: Settings):
    """Configure OpenTelemetry tracer provider if enabled."""
    global _OTEL_READY, _TRACER

    if not settings.otel_enabled:
        return None
    if _OTEL_READY and _TRACER is not None:
        return _TRACER

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:  # pragma: no cover - exercised when extras missing
        logger.warning("OTEL setup skipped (dependencies missing): %s", exc)
        return None

    if settings.otel_traces_exporter.lower() == "none":
        logger.info("OTEL traces exporter disabled by OTEL_TRACES_EXPORTER=none")
        return None

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
    if not endpoint.endswith("/v1/traces"):
        endpoint = f"{endpoint}/v1/traces"
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _TRACER = trace.get_tracer("agent_stack")
    _OTEL_READY = True
    return _TRACER


def get_tracer():
    try:
        from opentelemetry import trace
    except Exception:  # pragma: no cover
        return None
    return _TRACER or trace.get_tracer("agent_stack")


@contextlib.contextmanager
def start_span(name: str, *, parent_context=None, **attrs: Any):
    """Start a span when OTEL is available, else no-op."""
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    from opentelemetry.trace import Status, StatusCode

    with tracer.start_as_current_span(name, context=parent_context) as span:
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def extract_trace_context(headers: dict[str, str] | Any):
    try:
        from opentelemetry.propagate import get_global_textmap
    except Exception:  # pragma: no cover
        return None
    return get_global_textmap().extract(carrier=headers)


def inject_trace_headers(headers: dict[str, str]) -> None:
    try:
        from opentelemetry.propagate import get_global_textmap
    except Exception:  # pragma: no cover
        return
    get_global_textmap().inject(carrier=headers)


def current_trace_ids() -> tuple[str, str]:
    """Return current OTEL trace_id/span_id as hex strings."""
    try:
        from opentelemetry.trace import get_current_span
    except Exception:  # pragma: no cover
        return "", ""

    ctx = get_current_span().get_span_context()
    if not ctx or not ctx.is_valid:
        return "", ""
    return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"
