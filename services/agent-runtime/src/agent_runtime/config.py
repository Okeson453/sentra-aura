"""Agent-runtime service configuration."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentRuntimeConfig(BaseSettings):
    """Configuration for the agent-runtime service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="agent-runtime")

    # Provider Gateway
    provider_gateway_url: str = Field(default="http://localhost:8001")
    provider_gateway_timeout: float = Field(default=120.0)

    # Agent Registry
    agent_registry_url: str | None = Field(default=None)
    agent_registry_timeout: float = Field(default=30.0)

    # Content Graph
    content_graph_url: str | None = Field(default=None)
    content_graph_timeout: float = Field(default=30.0)

    # Event Bus
    nats_url: str | None = Field(default=None)

    # Policy Engine
    policy_engine_url: str | None = Field(default=None)

    # Research Service
    research_service_url: str | None = Field(default=None)

    # Execution
    max_concurrent_agents: int = Field(default=20)
    default_agent_timeout_seconds: float = Field(default=300.0)
    max_retries: int = Field(default=3)
    retry_base_delay_seconds: float = Field(default=1.0)
    retry_max_delay_seconds: float = Field(default=60.0)
    retry_jitter_percent: float = Field(default=0.2)

    # Sandbox
    sandbox_enabled: bool = Field(default=True)
    sandbox_timeout_seconds: float = Field(default=60.0)

    # Injection Defense
    injection_defense_enabled: bool = Field(default=True)
    injection_classifier_threshold: float = Field(default=0.7)

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(default=5)
    circuit_breaker_recovery_timeout: float = Field(default=30.0)
    circuit_breaker_half_open_max_calls: int = Field(default=3)

    # Cost
    default_budget_usd: float = Field(default=10.0)
    budget_alert_threshold: float = Field(default=0.8)

    # Observability
    jaeger_endpoint: str | None = Field(default=None)
    metrics_port: int = Field(default=9090)


config = AgentRuntimeConfig()
