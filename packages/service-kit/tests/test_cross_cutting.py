"""Tests for service-kit cross-cutting concerns."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from service_kit.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError,
    get_circuit_breaker, CircuitBreakerRegistry,
)
from service_kit.retry import with_retry, retry, RetryConfig, RetryExhaustedError
from service_kit.graceful_shutdown import GracefulShutdownManager


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        cb = CircuitBreaker("test")
        result = await cb.call(lambda: asyncio.sleep(0))
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3, recovery_timeout_seconds=60))

        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == "OPEN"
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(lambda: asyncio.sleep(0))

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, recovery_timeout_seconds=0.1))

        async def fail():
            raise RuntimeError("fail")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == "OPEN"
        await asyncio.sleep(0.15)

        # Should allow one call in half-open
        await cb.call(lambda: asyncio.sleep(0))
        assert cb.state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_closes_after_successes(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, recovery_timeout_seconds=0.1, success_threshold=2))

        async def fail():
            raise RuntimeError("fail")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        await asyncio.sleep(0.15)
        await cb.call(lambda: asyncio.sleep(0))
        await cb.call(lambda: asyncio.sleep(0))
        assert cb.state == "CLOSED"

    def test_metrics(self):
        cb = CircuitBreaker("test")
        metrics = cb.get_metrics()
        assert metrics["name"] == "test"
        assert metrics["state"] == "CLOSED"

    def test_registry(self):
        registry = CircuitBreakerRegistry()
        cb = registry.get("svc-1")
        assert cb.name == "svc-1"
        assert "svc-1" in registry.metrics()


class TestRetry:
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        async def success():
            return "ok"
        result = await with_retry(success, RetryConfig(max_attempts=3))
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        call_count = 0
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("fail")
            return "ok"

        result = await with_retry(flaky, RetryConfig(max_attempts=3, base_delay_seconds=0.01))
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        async def always_fail():
            raise RuntimeError("fail")

        with pytest.raises(RetryExhaustedError):
            await with_retry(always_fail, RetryConfig(max_attempts=2, base_delay_seconds=0.01))

    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        @retry(max_attempts=2, base_delay_seconds=0.01)
        async def decorated():
            raise RuntimeError("fail")

        with pytest.raises(RetryExhaustedError):
            await decorated()


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_hooks_executed(self):
        manager = GracefulShutdownManager(shutdown_timeout_seconds=5.0)
        hook_called = False

        async def hook():
            nonlocal hook_called
            hook_called = True

        manager.add_hook(hook)
        await manager.shutdown()
        assert hook_called is True
        assert manager.is_shutting_down() is True

    @pytest.mark.asyncio
    async def test_shutdown_hook_timeout(self):
        manager = GracefulShutdownManager(shutdown_timeout_seconds=0.1)

        async def slow_hook():
            await asyncio.sleep(1.0)

        manager.add_hook(slow_hook)
        await manager.shutdown()  # Should not raise, just log error
        assert manager.is_shutting_down() is True

    @pytest.mark.asyncio
    async def test_multiple_hooks(self):
        manager = GracefulShutdownManager()
        results = []

        async def hook1():
            results.append(1)
        async def hook2():
            results.append(2)

        manager.add_hook(hook1)
        manager.add_hook(hook2)
        await manager.shutdown()
        assert sorted(results) == [1, 2]

    def test_remove_hook(self):
        manager = GracefulShutdownManager()
        async def hook():
            pass
        manager.add_hook(hook)
        manager.remove_hook(hook)
        assert len(manager._hooks) == 0
