"""Configuration for the Clipping Engine.

Pydantic-settings based configuration with environment variable overrides.
"""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_INSECURE_JWT_DEFAULTS = frozenset({
    "change-me-in-production",
    "change-me-in-production-min-32-chars",
})


class ServiceConfig(BaseSettings):
    """Runtime configuration for the Clipping Engine."""

    model_config = SettingsConfigDict(
        env_prefix="CLIPPING_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="clipping-engine", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    log_level: str = Field(default="INFO", description="Logging level")
    port: int = Field(default=8080, ge=1024, le=65535, description="HTTP port")
    otel_endpoint: str | None = Field(default=None, description="OpenTelemetry collector endpoint")
    database_url: str = Field(default="sqlite:///./clipping_engine.db", description="Database connection URL")
    redis_url: str | None = Field(default=None, description="Redis connection URL")
    jwt_secret: str = Field(default="change-me-in-production", description="JWT signing secret")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    max_request_size_mb: int = Field(default=50, ge=1, le=500, description="Max request size in MB")
    request_timeout_seconds: float = Field(default=30.0, ge=5.0, le=300.0, description="Request timeout")
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    # Architecture §6 / §25 — optional override of ClipScore DEFAULT_WEIGHTS (JSON object)
    clip_score_weights_json: str = Field(default="", alias="CLIP_SCORE_WEIGHTS_JSON")

    media_renderer_url: str = Field(
        default="http://localhost:8081",
        description="Base URL of the media-renderer service for real clip renders",
    )
    asset_store_url: str | None = Field(
        default=None,
        description="Optional asset-store base URL for signed output URLs",
    )

    @model_validator(mode="after")
    def _reject_insecure_jwt_secret_in_production(self) -> "ServiceConfig":
        if self.is_production and (
            self.jwt_secret in _INSECURE_JWT_DEFAULTS or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be a strong, unique value of at least 32 "
                "characters in production (refusing the insecure default)"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.log_level in ("WARNING", "ERROR")
