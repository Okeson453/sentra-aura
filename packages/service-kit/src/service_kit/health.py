"""Health check registry for SentraAura services.

Provides /health and /ready endpoints with dependency checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from fastapi import APIRouter


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    name: str
    check_fn: Callable[[], Awaitable[tuple[HealthStatus, float]]]


class HealthCheckRegistry:
    """Registry of health checks for a service."""

    def __init__(self) -> None:
        self._checks: list[HealthCheck] = []

    def register(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[tuple[HealthStatus, float]]],
    ) -> None:
        """Register a health check."""
        self._checks.append(HealthCheck(name=name, check_fn=check_fn))

    async def check_all(self) -> dict[str, Any]:
        """Run all health checks and return aggregated status."""
        results: dict[str, Any] = {}
        overall = HealthStatus.HEALTHY

        for hc in self._checks:
            try:
                status, latency_ms = await hc.check_fn()
                results[hc.name] = {"status": status.value, "latency_ms": latency_ms}
                if status == HealthStatus.UNHEALTHY:
                    overall = HealthStatus.UNHEALTHY
                elif status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
                    overall = HealthStatus.DEGRADED
            except Exception as exc:
                results[hc.name] = {"status": HealthStatus.UNHEALTHY.value, "error": str(exc)}
                overall = HealthStatus.UNHEALTHY

        return {
            "status": overall.value,
            "checks": results,
        }


# Default health router for services
health_router = APIRouter()

_registry = HealthCheckRegistry()


@health_router.get("/health")
async def health_endpoint() -> dict[str, Any]:
    return await _registry.check_all()


@health_router.get("/ready")
async def ready_endpoint() -> dict[str, Any]:
    result = await _registry.check_all()
    if result["status"] == HealthStatus.UNHEALTHY.value:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=result)
    return result
