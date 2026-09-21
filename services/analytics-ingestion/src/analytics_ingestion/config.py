"""Configuration for the Analytics Ingestion Service."""
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


#: Repository-visible signing keys that must never be accepted in production.
_INSECURE_JWT_DEFAULTS = frozenset({
    "change-me-in-production",
    "change-me-in-production-min-32-chars",
})


class AnalyticsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="analytics-ingestion")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    metrics_port: int = Field(default=9090)
    database_url: str = Field(default="postgresql+asyncpg://sentra:sentra@localhost:5432/analytics_ingestion")
    redis_url: str = Field(default="redis://localhost:6379/4")
    warehouse_url: str = Field(default="clickhouse://localhost:8123/analytics")
    youtube_api_key: str = Field(default="")
    #: Daily YouTube Data API quota budget, used for real request accounting
    #: (see YouTubeAnalyticsClient). Google's default project allowance is
    #: 10,000 units/day and a videos.list call costs 1 unit per request.
    youtube_daily_quota_units: int = Field(default=10_000)
    nats_url: str = Field(default="nats://localhost:4222")

    # Authentication. Every route on this service previously served
    # unauthenticated callers because the app never registered the shared
    # middleware at all. The posture is fail-closed; a deployment opts out
    # explicitly (REQUIRE_AUTH=false) if it genuinely needs an open surface.
    #: Development default; the validator below refuses this value in
    #: production, where a real secret must be supplied.
    jwt_secret: str = Field(default="change-me-in-production-min-32-chars")
    jwt_algorithm: str = Field(default="HS256")
    require_auth: bool = Field(default=True)
    #: When True the acting tenant comes solely from the verified JWT claim and
    #: a caller that names a different tenant is rejected.
    enforce_tenant_isolation: bool = Field(default=True)
    batch_size: int = Field(default=100)
    flush_interval_seconds: int = Field(default=60)
    channel_ids: list[str] = Field(default=[])
    video_metrics_fetch_interval_seconds: int = Field(default=900)
    channel_health_check_interval_seconds: int = Field(default=300)
    max_videos_per_channel_fetch: int = Field(default=50)
    enable_background_ingestion: bool = Field(default=True)

    @model_validator(mode="after")
    def _reject_insecure_jwt_secret_in_production(self) -> "AnalyticsConfig":
        """Fail closed in production on a shared, repository-visible key.

        A well-known signing secret lets any caller mint a valid JWT and bypass
        authentication entirely (CWE-1188 / CWE-798). Development and test
        environments keep working on the default so the service stays runnable.
        """
        if self.environment.lower() == "production":
            if not self.jwt_secret or self.jwt_secret in _INSECURE_JWT_DEFAULTS:
                raise ValueError(
                    "JWT_SECRET must be set to a strong, unique value in "
                    "production (refusing the insecure default)"
                )
            if len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be at least 32 characters in production"
                )
        return self


config = AnalyticsConfig()
