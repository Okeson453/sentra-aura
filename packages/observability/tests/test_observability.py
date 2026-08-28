"""Tests for observability package."""
import pytest

from observability.tracing import get_tracer, trace_span, set_trace_id
from observability.logging import get_logger
from observability.metrics import get_metrics, Counter, Histogram, Gauge
from observability.llm_tracer import LLMTracer


def test_tracer_span():
    tracer = get_tracer("test-service")
    with trace_span(tracer, "test-op", attributes={"key": "val"}) as span:
        assert span.name == "test-op"
        assert span.attributes["key"] == "val"


def test_trace_id_context():
    set_trace_id("trace-123")
    from observability.tracing import get_current_trace_id
    assert get_current_trace_id() == "trace-123"


def test_counter():
    c = Counter("test_counter", "A test counter", labels=["service"])
    c.inc(1, service="s1")
    c.inc(2, service="s1")
    assert c.get(service="s1") == 3.0


def test_histogram():
    h = Histogram("test_hist", "A test histogram")
    h.observe(0.1)
    h.observe(0.5)
    assert h.get_count() == 2


def test_gauge():
    g = Gauge("test_gauge", "A test gauge")
    g.set(42.0)
    assert g.get() == 42.0


def test_llm_tracer():
    tracer = get_tracer("test")
    llm = LLMTracer(tracer)
    with llm.trace_completion(prompt="hello", provider="openai", model="gpt-4") as ctx:
        ctx.record_result(
            completion="world",
            prompt_tokens=1,
            completion_tokens=1,
            estimated_cost_usd=0.001,
        )
