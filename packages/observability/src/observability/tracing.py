"""OpenTelemetry tracing for SentraAura.

Every workflow execution carries a trace_id;
every agent LLM call is traced with prompt hash, completion hash,
token count, latency, and cost.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

# Context-local trace ID propagation
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_current_trace_id() -> str | None:
    """Get the current trace ID from context."""
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set the current trace ID in context."""
    _trace_id_var.set(trace_id)


class Tracer:
    """Simplified tracer interface compatible with OpenTelemetry."""

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        parent_trace_id: str | None = None,
    ) -> "Span":
        trace_id = parent_trace_id or _trace_id_var.get() or ""
        return Span(name, trace_id=trace_id, attributes=attributes or {})


class Span:
    """Active span context."""

    def __init__(self, name: str, trace_id: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.trace_id = trace_id
        self.attributes = attributes
        self._finished = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self) -> None:
        self._finished = True

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, *args: Any) -> None:
        self.finish()


def get_tracer(service_name: str) -> Tracer:
    """Get or create a tracer for the given service."""
    return Tracer(service_name)


@contextmanager
def trace_span(
    tracer: Tracer,
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Context manager for a traced span."""
    span = tracer.start_span(name, attributes=attributes)
    try:
        yield span
    finally:
        span.finish()
