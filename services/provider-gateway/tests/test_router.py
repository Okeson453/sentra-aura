"""Tests for Provider Gateway router, cost tracker, and adapters."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from provider_gateway.config import GatewayConfig, ProviderConfig
from provider_gateway.router import ProviderRouter, NoProviderAvailableError, AllProvidersFailedError
from provider_gateway.cost_tracker import CostTracker
from provider_gateway.llm_tracer import LLMTracer
from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability


class MockAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Mock adapter for testing routing logic."""

    def __init__(self, provider_id: str, capabilities: list[ProviderCapability], should_fail: bool = False) -> None:
        super().__init__(ProviderConfig(provider_id=provider_id, enabled=True))
        self._provider_id = provider_id
        self._capabilities = capabilities
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return self._capabilities

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Mock failure")
        return {"text": f"response from {self._provider_id}", "model": "mock-model"}

    async def _health_check_impl(self) -> bool:
        return not self.should_fail

    def estimate_cost(self, request: dict[str, Any]) -> float:
        return 0.001


@pytest.fixture
def config() -> GatewayConfig:
    return GatewayConfig(
        service_name="test-gateway",
        default_fallback_allowed=True,
        cost_budget_usd_per_channel_per_day=10.0,
    )


@pytest.fixture
def cost_tracker() -> CostTracker:
    return CostTracker()


@pytest.fixture
def router(config: GatewayConfig, cost_tracker: CostTracker) -> ProviderRouter:
    return ProviderRouter(config=config, cost_tracker=cost_tracker)


class TestProviderRouter:
    def test_register_and_list_providers(self, router: ProviderRouter) -> None:
        adapter = MockAdapter("mock-llm", [ProviderCapability.LLM_COMPLETE])
        router.register(adapter)
        providers = router.list_providers()
        assert len(providers) == 1
        assert providers[0]["provider_id"] == "mock-llm"
        assert "llm_complete" in providers[0]["capabilities"]

    @pytest.mark.asyncio
    async def test_route_success(self, router: ProviderRouter) -> None:
        adapter = MockAdapter("mock-llm", [ProviderCapability.LLM_COMPLETE])
        router.register(adapter)
        result = await router.route(
            capability=ProviderCapability.LLM_COMPLETE,
            request={"prompt": "hello"},
            channel_id="ch-1",
            task_type="test",
        )
        assert result.provider_id == "mock-llm"
        assert result.data["text"] == "response from mock-llm"
        assert result.fallback_used is False
        assert result.estimated_cost_usd == 0.001

    @pytest.mark.asyncio
    async def test_route_fallback(self, router: ProviderRouter) -> None:
        primary = MockAdapter("primary", [ProviderCapability.LLM_COMPLETE], should_fail=True)
        fallback = MockAdapter("fallback", [ProviderCapability.LLM_COMPLETE])
        router.register(primary)
        router.register(fallback)

        result = await router.route(
            capability=ProviderCapability.LLM_COMPLETE,
            request={"prompt": "hello"},
            preferred_provider="primary",
            channel_id="ch-1",
            task_type="test",
        )
        assert result.provider_id == "fallback"
        assert result.fallback_used is True
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_route_no_provider(self, router: ProviderRouter) -> None:
        with pytest.raises(NoProviderAvailableError):
            await router.route(
                capability=ProviderCapability.LLM_COMPLETE,
                request={"prompt": "hello"},
            )

    @pytest.mark.asyncio
    async def test_route_all_fail(self, router: ProviderRouter) -> None:
        adapter = MockAdapter("failing", [ProviderCapability.LLM_COMPLETE], should_fail=True)
        router.register(adapter)
        with pytest.raises(AllProvidersFailedError):
            await router.route(
                capability=ProviderCapability.LLM_COMPLETE,
                request={"prompt": "hello"},
            )

    @pytest.mark.asyncio
    async def test_route_budget_exceeded(self, router: ProviderRouter) -> None:
        adapter = MockAdapter("mock-llm", [ProviderCapability.LLM_COMPLETE])
        router.register(adapter)
        # Spend the budget
        for _ in range(10000):
            router.cost_tracker.record(
                provider_id="mock-llm",
                channel_id="ch-broke",
                task_type="test",
                estimated_cost=0.001,
                latency_ms=10.0,
            )
        with pytest.raises(AllProvidersFailedError):
            await router.route(
                capability=ProviderCapability.LLM_COMPLETE,
                request={"prompt": "hello"},
                channel_id="ch-broke",
                task_type="test",
            )

    @pytest.mark.asyncio
    async def test_health_check_all(self, router: ProviderRouter) -> None:
        healthy = MockAdapter("healthy", [ProviderCapability.LLM_COMPLETE])
        unhealthy = MockAdapter("unhealthy", [ProviderCapability.LLM_COMPLETE], should_fail=True)
        router.register(healthy)
        router.register(unhealthy)
        results = await router.health_check_all()
        assert results["healthy"] == "healthy"
        assert results["unhealthy"] == "degraded"

    def test_list_models(self, router: ProviderRouter) -> None:
        adapter = MockAdapter("mock-llm", [ProviderCapability.LLM_COMPLETE])
        router.register(adapter)
        models = router.list_models("mock-llm")
        assert models == []


class TestCostTracker:
    def test_record_and_report(self) -> None:
        tracker = CostTracker()
        tracker.record(
            provider_id="openai",
            channel_id="ch-1",
            task_type="script",
            estimated_cost=0.05,
            latency_ms=120.0,
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
        )
        report = tracker.get_usage_report(channel_id="ch-1")
        assert report["total_cost_usd"] == 0.05
        assert report["by_provider"]["openai"] == 0.05
        assert report["by_model"]["gpt-4o"] == 0.05
        assert report["invocation_count"] == 1
        assert report["total_tokens"] == 150

    def test_can_spend_budget(self) -> None:
        tracker = CostTracker()
        assert tracker.can_spend("ch-1", 5.0, 10.0) is True
        tracker.record(
            provider_id="openai",
            channel_id="ch-1",
            task_type="script",
            estimated_cost=8.0,
            latency_ms=100.0,
        )
        assert tracker.can_spend("ch-1", 5.0, 10.0) is False
        assert tracker.can_spend("ch-1", 1.5, 10.0) is True

    def test_export_records(self) -> None:
        tracker = CostTracker()
        tracker.record(
            provider_id="openai",
            channel_id="ch-1",
            task_type="script",
            estimated_cost=0.01,
            latency_ms=50.0,
        )
        exported = tracker.export_records()
        assert "openai" in exported
        assert "ch-1" in exported


class TestLLMTracer:
    def test_tracer_no_otel(self) -> None:
        tracer = LLMTracer(service_name="test", otel_endpoint=None)
        span = tracer.start_span(
            operation="complete",
            provider_id="openai",
            model="gpt-4o",
            channel_id="ch-1",
            task_type="script",
        )
        assert span is not None
        with span:
            tracer.record_completion(
                span_context=span,
                completion_tokens=50,
                latency_ms=100.0,
                estimated_cost_usd=0.05,
            )

    def test_record_fallback(self) -> None:
        tracer = LLMTracer(service_name="test")
        # Should not raise when OTel unavailable
        tracer.record_fallback("openai", "anthropic", "rate_limit")
