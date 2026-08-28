"""Service configuration for SentraAura.

Pydantic-based config with environment variable support.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    """Base configuration for all SentraAura services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="sentra-aura-service")

    # Database
    database_url: str | None = Field(default=None)
    database_pool_size: int = Field(default=10)

    # Redis
    redis_url: str | None = Field(default=None)

    # NATS
    nats_url: str | None = Field(default=None)

    # Vault
    vault_addr: str | None = Field(default=None)
    vault_token: str | None = Field(default=None)

    # Temporal
    temporal_host: str | None = Field(default=None)
    temporal_namespace: str = Field(default="default")

    # Provider Gateway
    provider_gateway_url: str | None = Field(default=None)

    # Control Plane
    control_plane_api_url: str | None = Field(default=None)

    # CORS
    cors_origins: list[str] = Field(default=["*"])


# Alias for backward compatibility
Settings = ServiceConfig
