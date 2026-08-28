"""Observability integration for SentraAura service kit.

Provides OpenTelemetry setup, tracing, and metrics integration.
Matches Architecture §10.2 and Backend Spec §10.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Simple tracer implementation when OpenTelemetry is not available
class _SimpleTracer:
    """Fallback tracer when OpenTelemetry is not installed."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> Any:
        return _SimpleSpan(name)

    def start_span(self, name: str, **kwargs: Any) -> Any:
        return _SimpleSpan(name)


class _SimpleSpan:
    """Fallback span implementation."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "_SimpleSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        logger.exception(f"Exception in span {self.name}: {exception}")

    def end(self) -> None:
        pass


_tracer: Any = _SimpleTracer()


def setup_opentelemetry(
    service_name: str = "sentraura",
    otlp_endpoint: str | None = None,
    jaeger_endpoint: str | None = None,
) -> None:
    """Configure OpenTelemetry tracing for a service.

    Falls back to simple logging tracer if OpenTelemetry is not installed.
    """
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider = TracerProvider()
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        logger.info(f"OpenTelemetry configured for {service_name}")
    except ImportError:
        logger.warning("OpenTelemetry not installed, using simple tracer fallback")
        _tracer = _SimpleTracer()


def get_tracer(name: str | None = None) -> Any:
    """Get the current tracer instance."""
    global _tracer
    if name:
        try:
            from opentelemetry import trace
            return trace.get_tracer(name)
        except ImportError:
            pass
    return _tracer


@contextmanager
def trace_span(name: str, **attributes: Any) -> Generator[Any, None, None]:
    """Context manager for creating a trace span."""
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span
    except Exception:
        logger.exception(f"Error in trace span {name}")
        yield _SimpleSpan(name)


__all__ = [
    "setup_opentelemetry",
    "get_tracer",
    "trace_span",
]
