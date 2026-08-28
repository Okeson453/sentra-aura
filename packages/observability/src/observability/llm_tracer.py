"""LLM-specific tracing for SentraAura.

Per-call telemetry: prompt hash, completion hash, token count,
latency, cost, model version, provider.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from observability.tracing import Span, Tracer, trace_span
from observability.logging import get_logger

logger = get_logger(__name__)


class LLMTracer:
    """Trace LLM/TTS/image/video calls through the Provider Gateway."""

    def __init__(self, tracer: Tracer) -> None:
        self.tracer = tracer

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def trace_completion(
        self,
        *,
        prompt: str,
        provider: str,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> "LLMCallContext":
        """Start tracing an LLM completion call."""
        return LLMCallContext(
            tracer=self.tracer,
            prompt=prompt,
            prompt_hash=self._hash(prompt),
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class LLMCallContext:
    """Context manager for a single LLM call trace."""

    def __init__(
        self,
        *,
        tracer: Tracer,
        prompt: str,
        prompt_hash: str,
        provider: str,
        model: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> None:
        self.tracer = tracer
        self.prompt = prompt
        self.prompt_hash = prompt_hash
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._span: Span | None = None
        self._start_time: float = 0.0

    def __enter__(self) -> "LLMCallContext":
        self._start_time = time.perf_counter()
        self._span = self.tracer.start_span(
            "llm.completion",
            attributes={
                "llm.provider": self.provider,
                "llm.model": self.model,
                "llm.prompt_hash": self.prompt_hash,
                "llm.temperature": self.temperature,
                "llm.max_tokens": self.max_tokens,
            },
        )
        return self

    def record_result(
        self,
        *,
        completion: str,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
    ) -> None:
        if self._span is None:
            return
        self._span.set_attribute("llm.completion_hash", hashlib.sha256(completion.encode()).hexdigest()[:16])
        self._span.set_attribute("llm.prompt_tokens", prompt_tokens)
        self._span.set_attribute("llm.completion_tokens", completion_tokens)
        self._span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)
        self._span.set_attribute("llm.estimated_cost_usd", estimated_cost_usd)

    def __exit__(self, *args: Any) -> None:
        if self._span is not None:
            latency_ms = (time.perf_counter() - self._start_time) * 1000
            self._span.set_attribute("llm.latency_ms", latency_ms)
            self._span.finish()
            logger.info(
                "LLM call completed",
                extra={
                    "provider": self.provider,
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "prompt_hash": self.prompt_hash,
                },
            )
