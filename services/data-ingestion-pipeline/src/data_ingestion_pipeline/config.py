"""Configuration for data-ingestion-pipeline.

Pydantic Settings with env-file support, validation, and secrets handling.
Matches Architecture §3.1 and Backend Spec §2.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service identity
    service_name: str = "data-ingestion-pipeline"
    service_version: str = "0.1.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # HTTP server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")

    # Database
    database_url: str = Field(default="postgresql+psycopg2://sentraaura:sentraaura@localhost:5432/sentraaura", alias="DATABASE_URL")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # Redis / Cache
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=300, alias="CACHE_TTL_SECONDS")

    # NATS
    nats_url: str = Field(default="nats://localhost:4222", alias="NATS_URL")
    nats_max_reconnect: int = Field(default=10, alias="NATS_MAX_RECONNECT")

    # Temporal
    temporal_host: str = Field(default="localhost:7233", alias="TEMPORAL_HOST")
    temporal_namespace: str = Field(default="sentraaura", alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field(default="sentraaura-tasks", alias="TEMPORAL_TASK_QUEUE")

    # Security
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_minutes: int = Field(default=60, alias="JWT_EXPIRY_MINUTES")
    api_key_header: str = Field(default="X-API-Key", alias="API_KEY_HEADER")
    allowed_tenants: list[str] = Field(default_factory=list, alias="ALLOWED_TENANTS")

    # Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    otel_endpoint: str | None = Field(default=None, alias="OTEL_ENDPOINT")
    prometheus_port: int = Field(default=9090, alias="PROMETHEUS_PORT")
    health_check_timeout_seconds: float = Field(default=5.0, alias="HEALTH_CHECK_TIMEOUT_SECONDS")

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_HEADERS")

    # Rate limiting
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    # Circuit breaker
    circuit_breaker_failure_threshold: int = Field(default=5, alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_recovery_timeout: int = Field(default=30, alias="CIRCUIT_BREAKER_RECOVERY_TIMEOUT")
    circuit_breaker_expected_exception: str = Field(default="Exception", alias="CIRCUIT_BREAKER_EXPECTED_EXCEPTION")

    # Retry policy
    retry_max_attempts: int = Field(default=3, alias="RETRY_MAX_ATTEMPTS")
    retry_backoff_factor: float = Field(default=2.0, alias="RETRY_BACKOFF_FACTOR")
    retry_max_delay_seconds: float = Field(default=60.0, alias="RETRY_MAX_DELAY_SECONDS")

    # Feature flags
    feature_flags: dict[str, bool] = Field(default_factory=dict, alias="FEATURE_FLAGS")

    # Cost control
    max_budget_usd_per_task: float = Field(default=10.0, alias="MAX_BUDGET_USD_PER_TASK")
    cost_alert_threshold_usd: float = Field(default=100.0, alias="COST_ALERT_THRESHOLD_USD")

        # Data ingestion specific
    ingestion_batch_size: int = Field(default=100, alias="INGESTION_BATCH_SIZE")
    ingestion_poll_interval_seconds: int = Field(default=300, alias="INGESTION_POLL_INTERVAL_SECONDS")
    max_ingestion_jobs: int = Field(default=10, alias="MAX_INGESTION_JOBS")
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    google_trends_api_key: str | None = Field(default=None, alias="GOOGLE_TRENDS_API_KEY")
    rss_feed_urls: list[str] = Field(default_factory=list, alias="RSS_FEED_URLS")
    social_listening_keywords: list[str] = Field(default_factory=list, alias="SOCIAL_LISTENING_KEYWORDS")
    collector_timeout_seconds: int = Field(default=30, alias="COLLECTOR_TIMEOUT_SECONDS")
    normalizer_timeout_seconds: int = Field(default=10, alias="NORMALIZER_TIMEOUT_SECONDS")


    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = ('development', 'staging', 'production')
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v}")
        return v.upper()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("allowed_tenants", mode="before")
    @classmethod
    def _parse_allowed_tenants(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v

    @field_validator("feature_flags", mode="before")
    @classmethod
    def _parse_feature_flags(cls, v: Any) -> dict[str, bool]:
        if isinstance(v, str):
            result: dict[str, bool] = {}
            for item in v.split(","):
                if "=" in item:
                    key, val = item.strip().split("=", 1)
                    result[key.strip()] = val.strip().lower() in ("true", "1", "yes", "on")
            return result
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
