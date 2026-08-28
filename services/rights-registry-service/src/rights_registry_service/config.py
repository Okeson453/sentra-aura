"""Configuration for the Rights Registry Service.

Pydantic-settings based configuration with environment variable overrides.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    """Runtime configuration for the Rights Registry Service."""

    model_config = SettingsConfigDict(
        env_prefix="RIGHTS_REGISTRY_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="rights-registry-service", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    log_level: str = Field(default="INFO", description="Logging level")
    port: int = Field(default=8080, ge=1024, le=65535, description="HTTP port")
    otel_endpoint: str | None = Field(default=None, description="OpenTelemetry collector endpoint")
    database_url: str = Field(default="sqlite:///./rights_registry_service.db", description="Database connection URL")
    redis_url: str | None = Field(default=None, description="Redis connection URL")
    jwt_secret: str = Field(default="change-me-in-production", description="JWT signing secret")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    max_request_size_mb: int = Field(default=50, ge=1, le=500, description="Max request size in MB")
    request_timeout_seconds: float = Field(default=30.0, ge=5.0, le=300.0, description="Request timeout")
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    @property
    def is_production(self) -> bool:
        return self.log_level in ("WARNING", "ERROR")
