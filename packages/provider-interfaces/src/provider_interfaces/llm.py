"""LLM provider interface for SentraAura.

Matches Architecture §11.1 exactly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class LLMConfig:
    """Configuration for an LLM completion request."""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: list[str] | None = None
    response_format: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    timeout_seconds: float = 120.0


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def complete(self, prompt: str, config: LLMConfig | None = None) -> LLMResponse:
        """Generate a completion for the given prompt."""
        ...

    @abstractmethod
    async def stream_complete(self, prompt: str, config: LLMConfig | None = None) -> AsyncIterator[str]:
        """Stream completion tokens for the given prompt."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        ...

    @abstractmethod
    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
