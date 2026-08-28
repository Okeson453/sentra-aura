"""Base provider adapter with circuit breaker, health checks, and capability discovery."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Generic, TypeVar

from provider_gateway.config import ProviderConfig


class ProviderHealth(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()
    DISABLED = auto()


class ProviderCapability(Enum):
    LLM_COMPLETE = "llm_complete"
    LLM_STREAM = "llm_stream"
    EMBED = "embed"
    TTS = "tts"
    IMAGE_GENERATE = "image_generate"
    IMAGE_EDIT = "image_edit"
    VIDEO_GENERATE = "video_generate"
    VIDEO_EDIT = "video_edit"
    SEARCH = "search"
    TRANSCRIBE = "transcribe"
    MODERATE = "moderate"


@dataclass
class CircuitBreaker:
    """Circuit breaker state machine."""

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    _failures: int = field(default=0, repr=False)
    _last_failure_time: float | None = field(default=None, repr=False)
    _state: str = field(default="closed", repr=False)

    def record_success(self) -> None:
        if self._state == "half_open":
            self._state = "closed"
            self._failures = 0
            self._last_failure_time = None
        elif self._state == "closed":
            self._failures = max(0, self._failures - 1)

    def record_failure(self) -> bool:
        """Record a failure. Returns True if the circuit just opened."""
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.failure_threshold and self._state != "open":
            self._state = "open"
            return True
        return False

    def can_execute(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout_seconds:
                    self._state = "half_open"
                    return True
            return False
        return self._state == "half_open"

    @property
    def state(self) -> str:
        return self._state


T = TypeVar("T")


class BaseProviderAdapter(ABC, Generic[T]):
    """Abstract base for all provider adapters."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._health = ProviderHealth.HEALTHY
        self._circuit = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=30.0,
        )
        self._last_health_check: float = 0.0
        self._health_check_interval_seconds: float = 30.0

    @property
    @abstractmethod
    def provider_id(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[ProviderCapability]:
        ...

    @property
    def health(self) -> ProviderHealth:
        return self._health

    @property
    def circuit_state(self) -> str:
        return self._circuit.state

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    async def execute(self, request: T, timeout: float | None = None) -> dict[str, Any]:
        """Execute a request with circuit breaker and health tracking."""
        if not self.config.enabled:
            raise ProviderDisabledError(self.provider_id)
        if not self._circuit.can_execute():
            raise CircuitOpenError(self.provider_id)

        to = timeout or self.config.timeout_seconds
        try:
            result = await asyncio.wait_for(self._execute(request), timeout=to)
            self._circuit.record_success()
            self._health = ProviderHealth.HEALTHY
            return result
        except asyncio.TimeoutError:
            self._circuit.record_failure()
            self._health = ProviderHealth.DEGRADED
            raise ProviderTimeoutError(self.provider_id, to)
        except Exception as exc:
            opened = self._circuit.record_failure()
            self._health = ProviderHealth.UNHEALTHY if opened else ProviderHealth.DEGRADED
            raise ProviderExecutionError(self.provider_id, str(exc)) from exc

    @abstractmethod
    async def _execute(self, request: T) -> dict[str, Any]:
        """Provider-specific execution logic."""
        ...

    async def health_check(self, force: bool = False) -> ProviderHealth:
        """Run a health check, respecting caching interval unless forced."""
        now = time.monotonic()
        if not force and (now - self._last_health_check) < self._health_check_interval_seconds:
            return self._health
        self._last_health_check = now
        try:
            healthy = await self._health_check_impl()
            self._health = ProviderHealth.HEALTHY if healthy else ProviderHealth.DEGRADED
        except Exception:
            self._health = ProviderHealth.UNHEALTHY
        return self._health

    @abstractmethod
    async def _health_check_impl(self) -> bool:
        """Provider-specific health check."""
        ...

    def estimate_cost(self, request: T) -> float:
        """Estimate cost in USD for a request. Override per provider."""
        return 0.0


class ProviderDisabledError(Exception):
    def __init__(self, provider_id: str) -> None:
        super().__init__(f"Provider {provider_id} is disabled")
        self.provider_id = provider_id


class CircuitOpenError(Exception):
    def __init__(self, provider_id: str) -> None:
        super().__init__(f"Circuit breaker open for provider {provider_id}")
        self.provider_id = provider_id


class ProviderTimeoutError(Exception):
    def __init__(self, provider_id: str, timeout: float) -> None:
        super().__init__(f"Provider {provider_id} timed out after {timeout}s")
        self.provider_id = provider_id
        self.timeout = timeout


class ProviderExecutionError(Exception):
    def __init__(self, provider_id: str, reason: str) -> None:
        super().__init__(f"Provider {provider_id} execution failed: {reason}")
        self.provider_id = provider_id
        self.reason = reason
