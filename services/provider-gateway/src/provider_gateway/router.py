"""Capability-based provider router with fallback chains and cost-aware selection."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, TypeVar

from provider_gateway.adapters.base import (
    BaseProviderAdapter,
    ProviderCapability,
    ProviderDisabledError,
    CircuitOpenError,
    ProviderTimeoutError,
    ProviderExecutionError,
)
from provider_gateway.config import GatewayConfig
from provider_gateway.cost_tracker import CostTracker

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class RouteResult:
    """Result of a routed provider call."""

    data: dict[str, Any]
    provider_id: str
    model: str | None
    latency_ms: float
    fallback_used: bool
    estimated_cost_usd: float


class ProviderRouter:
    """Routes requests to the best available provider with fallback support."""

    def __init__(
        self,
        config: GatewayConfig,
        cost_tracker: CostTracker,
    ) -> None:
        self.config = config
        self.cost_tracker = cost_tracker
        self._adapters: dict[str, BaseProviderAdapter[Any]] = {}
        self._capability_index: dict[ProviderCapability, list[str]] = {}
        self._lock = asyncio.Lock()

    def register(self, adapter: BaseProviderAdapter[Any]) -> None:
        """Register a provider adapter."""
        self._adapters[adapter.provider_id] = adapter
        for cap in adapter.capabilities:
            self._capability_index.setdefault(cap, []).append(adapter.provider_id)
        logger.info("Registered provider %s with capabilities %s", adapter.provider_id, [c.value for c in adapter.capabilities])

    def unregister(self, provider_id: str) -> None:
        """Unregister a provider adapter."""
        adapter = self._adapters.pop(provider_id, None)
        if adapter:
            for cap in adapter.capabilities:
                if cap in self._capability_index:
                    self._capability_index[cap] = [
                        pid for pid in self._capability_index[cap] if pid != provider_id
                    ]

    async def route(
        self,
        capability: ProviderCapability,
        request: dict[str, Any],
        preferred_provider: str | None = None,
        fallback_allowed: bool | None = None,
        channel_id: str | None = None,
        task_type: str | None = None,
    ) -> RouteResult:
        """Route a request to the best provider for the given capability."""
        fallback = fallback_allowed if fallback_allowed is not None else self.config.default_fallback_allowed
        candidate_ids = self._capability_index.get(capability, [])
        if not candidate_ids:
            raise NoProviderAvailableError(capability)

        # Preferred provider first
        ordered = list(candidate_ids)
        if preferred_provider and preferred_provider in ordered:
            ordered.remove(preferred_provider)
            ordered.insert(0, preferred_provider)

        # Sort by health and circuit state
        ordered = self._sort_by_health(ordered)

        last_error: Exception | None = None
        start_time = time.perf_counter()

        for provider_id in ordered:
            adapter = self._adapters.get(provider_id)
            if not adapter:
                continue

            # Cost budget check
            if channel_id and not self.cost_tracker.can_spend(
                channel_id=channel_id,
                estimated_cost=adapter.estimate_cost(request),
                budget=self.config.cost_budget_usd_per_channel_per_day,
            ):
                logger.warning("Cost budget exceeded for channel %s on provider %s", channel_id, provider_id)
                continue

            try:
                result = await adapter.execute(request)
                latency_ms = (time.perf_counter() - start_time) * 1000
                cost = adapter.estimate_cost(request)

                # Record cost
                if channel_id:
                    self.cost_tracker.record(
                        provider_id=provider_id,
                        channel_id=channel_id,
                        task_type=task_type or "unknown",
                        estimated_cost=cost,
                        latency_ms=latency_ms,
                    )

                return RouteResult(
                    data=result,
                    provider_id=provider_id,
                    model=result.get("model"),
                    latency_ms=latency_ms,
                    fallback_used=provider_id != preferred_provider if preferred_provider else False,
                    estimated_cost_usd=cost,
                )
            except (ProviderDisabledError, CircuitOpenError, ProviderTimeoutError, ProviderExecutionError) as exc:
                last_error = exc
                logger.warning("Provider %s failed for capability %s: %s", provider_id, capability.value, exc)
                if not fallback:
                    break
                continue

        latency_ms = (time.perf_counter() - start_time) * 1000
        raise AllProvidersFailedError(capability, last_error, latency_ms)

    def _sort_by_health(self, provider_ids: list[str]) -> list[str]:
        """Sort providers by health status (healthy first, then degraded, then unhealthy)."""

        def sort_key(pid: str) -> tuple[int, int]:
            adapter = self._adapters.get(pid)
            if not adapter:
                return (3, 0)
            health_order = {"HEALTHY": 0, "DEGRADED": 1, "UNHEALTHY": 2}
            h = health_order.get(adapter.health.name, 3)
            # Circuit closed is better
            c = 0 if adapter.circuit_state == "closed" else 1
            return (h, c)

        return sorted(provider_ids, key=sort_key)

    async def health_check_all(self) -> dict[str, str]:
        """Run health checks on all registered providers."""
        results: dict[str, str] = {}
        tasks = {
            pid: asyncio.create_task(adapter.health_check())
            for pid, adapter in self._adapters.items()
        }
        for pid, task in tasks.items():
            try:
                health = await asyncio.wait_for(task, timeout=10.0)
                results[pid] = health.name.lower()
            except asyncio.TimeoutError:
                results[pid] = "unhealthy"
        return results

    def list_providers(self) -> list[dict[str, Any]]:
        """List all registered providers with their capabilities and status."""
        return [
            {
                "provider_id": pid,
                "name": pid.replace("_", " ").title(),
                "status": "active" if adapter.config.enabled else "disabled",
                "models": getattr(adapter, "models", []),
                "capabilities": [c.value for c in adapter.capabilities],
                "health": adapter.health.name.lower(),
                "circuit_state": adapter.circuit_state,
            }
            for pid, adapter in self._adapters.items()
        ]

    def list_models(self, provider_id: str) -> list[dict[str, Any]]:
        """List models for a specific provider."""
        adapter = self._adapters.get(provider_id)
        if not adapter:
            raise ValueError(f"Unknown provider: {provider_id}")
        return getattr(adapter, "models", [])


class NoProviderAvailableError(Exception):
    def __init__(self, capability: ProviderCapability) -> None:
        super().__init__(f"No provider available for capability: {capability.value}")
        self.capability = capability


class AllProvidersFailedError(Exception):
    def __init__(self, capability: ProviderCapability, last_error: Exception | None, latency_ms: float) -> None:
        super().__init__(f"All providers failed for capability {capability.value}: {last_error}")
        self.capability = capability
        self.last_error = last_error
        self.latency_ms = latency_ms
