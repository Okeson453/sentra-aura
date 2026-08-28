"""Tests for service-kit package."""
import pytest

from service_kit.config import ServiceConfig
from service_kit.health import HealthCheckRegistry, HealthStatus


def test_service_config_defaults():
    cfg = ServiceConfig()
    assert cfg.environment == "local"
    assert cfg.log_level == "INFO"


def test_health_registry():
    reg = HealthCheckRegistry()
    async def always_healthy():
        return HealthStatus.HEALTHY, 1.0
    reg.register("db", always_healthy)
    import asyncio
    result = asyncio.run(reg.check_all())
    assert result["status"] == "healthy"
    assert "db" in result["checks"]
