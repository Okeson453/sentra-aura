"""Service Kit — shared utilities for SentraAura microservices.

Provides structured logging, metrics, middleware, lifespan management,
circuit breakers, retry logic, and graceful shutdown.
"""
from service_kit.logging_config import configure_logging, get_logger
from service_kit.metrics import MetricsCollector, get_metrics_collector
from service_kit.middleware import (
    MetricsMiddleware,
    RequestIDMiddleware,
    TenantResolutionMiddleware,
    AuthenticationMiddleware,
)
from service_kit.lifespan import create_lifespan
from service_kit.observability import setup_opentelemetry, get_tracer
from service_kit.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    CircuitBreakerRegistry,
)
from service_kit.retry import with_retry, retry, RetryConfig, RetryExhaustedError
from service_kit.graceful_shutdown import GracefulShutdownManager, FastAPIShutdownHandler

__all__ = [
    "configure_logging",
    "get_logger",
    "MetricsCollector",
    "get_metrics_collector",
    "MetricsMiddleware",
    "RequestIDMiddleware",
    "TenantResolutionMiddleware",
    "AuthenticationMiddleware",
    "create_lifespan",
    "setup_opentelemetry",
    "get_tracer",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "get_circuit_breaker",
    "CircuitBreakerRegistry",
    "with_retry",
    "retry",
    "RetryConfig",
    "RetryExhaustedError",
    "GracefulShutdownManager",
    "FastAPIShutdownHandler",
]
