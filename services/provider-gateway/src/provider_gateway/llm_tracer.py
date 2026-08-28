"""OpenTelemetry LLM tracer wired as additive exporter to Jaeger.

Emits spans for every LLM invocation with token counts, latency,
cost estimates, and fallback chain metadata.
"""

from __future__ import annotations

import logging
import time
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMTracer:
    """Traces LLM calls via OpenTelemetry, additive to Jaeger."""

    def __init__(self, service_name: str = "provider-gateway", otel_endpoint: str | None = None) -> None:
        self.service_name = service_name
        self._tracer: Any = None
        self._provider: Any = None

        if _OTEL_AVAILABLE:
            self._provider = TracerProvider()
            trace.set_tracer_provider(self._provider)
            if otel_endpoint:
                exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
                self._provider.add_span_processor(BatchSpanProcessor(exporter))
            self._tracer = trace.get_tracer(service_name)
        else:
            logger.warning("OpenTelemetry not installed; LLM tracing disabled")

    def start_span(
        self,
        operation: str,
        provider_id: str,
        model: str | None,
        channel_id: str | None,
        task_type: str | None,
        prompt_tokens: int = 0,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Start an LLM invocation span. Returns a context manager or None."""
        if self._tracer is None:
            return _NoOpSpan()

        attributes = {
            "llm.provider": provider_id,
            "llm.model": model or "unknown",
            "llm.operation": operation,
            "llm.prompt_tokens": prompt_tokens,
            "llm.temperature": temperature or 0.0,
        }
        if channel_id:
            attributes["channel.id"] = channel_id
        if task_type:
            attributes["task.type"] = task_type
        if max_tokens:
            attributes["llm.max_tokens"] = max_tokens

        return self._tracer.start_as_current_span(
            name=f"llm.{operation}",
            attributes=attributes,
        )

    def record_completion(
        self,
        span_context: Any,
        completion_tokens: int,
        latency_ms: float,
        estimated_cost_usd: float,
        fallback_used: bool = False,
        error: Exception | None = None,
    ) -> None:
        """Record completion details on an active span."""
        if span_context is None or not _OTEL_AVAILABLE:
            return

        try:
            span = trace.get_current_span()
            span.set_attribute("llm.completion_tokens", completion_tokens)
            span.set_attribute("llm.total_tokens", span.attributes.get("llm.prompt_tokens", 0) + completion_tokens)
            span.set_attribute("llm.latency_ms", latency_ms)
            span.set_attribute("llm.estimated_cost_usd", estimated_cost_usd)
            span.set_attribute("llm.fallback_used", fallback_used)

            if error:
                span.set_status(Status(StatusCode.ERROR, str(error)))
                span.record_exception(error)
            else:
                span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            logger.warning("Failed to record completion on span: %s", exc)

    def record_fallback(
        self,
        original_provider: str,
        fallback_provider: str,
        reason: str,
    ) -> None:
        """Record a fallback event as a separate span."""
        if self._tracer is None or not _OTEL_AVAILABLE:
            return
        with self._tracer.start_as_current_span("llm.fallback") as span:
            span.set_attribute("fallback.from_provider", original_provider)
            span.set_attribute("fallback.to_provider", fallback_provider)
            span.set_attribute("fallback.reason", reason)


class _NoOpSpan:
    """No-op span context manager when OTel is unavailable."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass
