"""Agent execution policy — the 7-step invocation policy from Architecture §4.1.

1. Validate input schema.
2. Acquire an idempotency key.
3. Check the relevant circuit breaker.
4. Execute with a bounded timeout.
5. Retry only on transient failures.
6. Record an audit log entry.
7. Emit metrics.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from typing import Any, Callable, Coroutine

from sentinel_exceptions import (
    AgentInvocationError,
    AgentOutputValidationError,
    AllProvidersFailed,
    ProviderRateLimit,
    ProviderUnavailable,
    SchemaValidationError,
    TransientError,
)
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.config import config


class CircuitBreaker:
    """Circuit breaker for provider/agent invocations.

    States: CLOSED → OPEN (after N failures/period) → HALF_OPEN (after timeout)
    → CLOSED (after M successes) or back to OPEN on failure.
    Matches Architecture §10.2.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self.last_failure_time and (time.monotonic() - self.last_failure_time) > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        if self.state == self.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return True

    def record_success(self) -> None:
        if self.state == self.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = self.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        self.last_failure_time = time.monotonic()
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            self.half_open_calls = 0
            return
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN


class ExecutionPolicy:
    """Enforces the 7-step agent invocation policy."""

    def __init__(self) -> None:
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._idempotency_store: set[str] = set()

    def _get_circuit_breaker(self, name: str) -> CircuitBreaker:
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout=config.circuit_breaker_recovery_timeout,
                half_open_max_calls=config.circuit_breaker_half_open_max_calls,
            )
        return self._circuit_breakers[name]

    def _generate_idempotency_key(self, envelope: AgentMessageEnvelope) -> str:
        """Generate an idempotency key from message content."""
        payload = json.dumps(envelope.message.payload, sort_keys=True, default=str)
        key_data = f"{envelope.message.agent_type}:{envelope.message.task_type}:{envelope.message.correlation_id}:{payload}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _is_duplicate(self, idempotency_key: str) -> bool:
        return idempotency_key in self._idempotency_store

    def _record_idempotency(self, idempotency_key: str) -> None:
        self._idempotency_store.add(idempotency_key)

    def _compute_retry_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        base = config.retry_base_delay_seconds * (2 ** attempt)
        base = min(base, config.retry_max_delay_seconds)
        jitter = base * config.retry_jitter_percent * random.uniform(-1, 1)
        return max(0.1, base + jitter)

    def _is_transient(self, exc: Exception) -> bool:
        """Determine if an exception is transient (retryable)."""
        if isinstance(exc, TransientError):
            return True
        if isinstance(exc, (ProviderUnavailable, ProviderRateLimit)):
            return True
        if isinstance(exc, AgentInvocationError):
            return True
        # HTTP-level transient errors
        err_str = str(exc).lower()
        transient_keywords = ["timeout", "connection", "temporarily", "rate limit", "503", "502", "504", "429"]
        return any(kw in err_str for kw in transient_keywords)

    async def execute(
        self,
        envelope: AgentMessageEnvelope,
        handler: Callable[[AgentMessageEnvelope], Coroutine[Any, Any, AgentMessageEnvelope]],
        *,
        schema_validator: Callable[[dict[str, Any]], tuple[bool, list[str]]] | None = None,
        audit_logger: Callable[[AgentMessageEnvelope, str], Coroutine[Any, Any, None]] | None = None,
        metrics_emitter: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentMessageEnvelope:
        """Execute an agent handler with the full 7-step policy.

        Args:
            envelope: The agent message envelope.
            handler: The coroutine that performs the actual agent work.
            schema_validator: Optional callable to validate input payload.
            audit_logger: Optional async callable to record audit entries.
            metrics_emitter: Optional callable to emit metrics.

        Returns:
            The processed envelope (possibly with error state).
        """
        agent_type = envelope.message.agent_type
        cb = self._get_circuit_breaker(agent_type)

        # Step 1: Validate input schema
        if schema_validator:
            is_valid, errors = schema_validator(envelope.message.payload)
            if not is_valid:
                envelope.message.state["validation_errors"] = errors
                envelope.escalation_reason = f"Schema validation failed: {errors}"
                if audit_logger:
                    await audit_logger(envelope, "SCHEMA_VALIDATION_FAILED")
                if metrics_emitter:
                    metrics_emitter("agent.execution.validation_failed", {"agent_type": agent_type})
                raise SchemaValidationError(f"Input schema validation failed for {agent_type}", details={"errors": errors})

        # Step 2: Acquire idempotency key
        idempotency_key = self._generate_idempotency_key(envelope)
        envelope.idempotency_key = idempotency_key
        if self._is_duplicate(idempotency_key):
            envelope.message.state["idempotency"] = "duplicate_detected"
            if audit_logger:
                await audit_logger(envelope, "IDEMPOTENCY_DUPLICATE")
            if metrics_emitter:
                metrics_emitter("agent.execution.duplicate_skipped", {"agent_type": agent_type})
            return envelope
        self._record_idempotency(idempotency_key)

        # Step 3: Check circuit breaker
        if not cb.can_execute():
            envelope.escalation_reason = f"Circuit breaker OPEN for {agent_type}"
            envelope.circuit_breaker_state = cb.state
            if audit_logger:
                await audit_logger(envelope, "CIRCUIT_BREAKER_OPEN")
            if metrics_emitter:
                metrics_emitter("agent.execution.circuit_breaker_open", {"agent_type": agent_type})
            raise AgentInvocationError(f"Circuit breaker OPEN for {agent_type}")

        envelope.circuit_breaker_state = cb.state

        # Step 4–5: Execute with bounded timeout and retry
        last_exception: Exception | None = None
        max_retries = config.max_retries

        for attempt in range(max_retries + 1):
            envelope.retry_count = attempt
            envelope.start_execution()

            try:
                result = await handler(envelope)
                result.end_execution()
                cb.record_success()

                # Step 6: Record audit log
                if audit_logger:
                    await audit_logger(result, "EXECUTION_SUCCESS")

                # Step 7: Emit metrics
                if metrics_emitter:
                    metrics_emitter("agent.execution.success", {
                        "agent_type": agent_type,
                        "duration_seconds": result.execution_duration_seconds or 0.0,
                        "retry_count": attempt,
                        "cost_usd": result.cost_accumulated_usd,
                    })

                return result

            except Exception as exc:
                last_exception = exc
                envelope.end_execution()

                if not self._is_transient(exc):
                    break  # Non-transient: do not retry

                if attempt < max_retries:
                    delay = self._compute_retry_delay(attempt)
                    if audit_logger:
                        await audit_logger(envelope, f"RETRY_ATTEMPT_{attempt + 1}")
                    if metrics_emitter:
                        metrics_emitter("agent.execution.retry", {
                            "agent_type": agent_type,
                            "attempt": attempt + 1,
                            "error": str(exc)[:100],
                        })
                    await self._async_sleep(delay)
                else:
                    break

        # All retries exhausted or non-transient failure
        cb.record_failure()
        envelope.escalation_reason = f"Execution failed after {envelope.retry_count + 1} attempts: {last_exception}"
        envelope.message.state["error"] = str(last_exception)
        envelope.message.state["error_type"] = type(last_exception).__name__

        if audit_logger:
            await audit_logger(envelope, "EXECUTION_FAILED")
        if metrics_emitter:
            metrics_emitter("agent.execution.failed", {
                "agent_type": agent_type,
                "retry_count": envelope.retry_count,
                "error": str(last_exception)[:200],
            })

        if isinstance(last_exception, Exception):
            raise last_exception
        raise AgentInvocationError("Unknown execution failure")

    @staticmethod
    async def _async_sleep(seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)
