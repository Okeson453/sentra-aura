"""Configuration for the Analytics Ingestion Service."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    nats_url: str = Field(default="nats://localhost:4222")
    batch_size: int = Field(default=100)
    flush_interval_seconds: int = Field(default=60)
    channel_ids: list[str] = Field(default=[])
    video_metrics_fetch_interval_seconds: int = Field(default=900)
    channel_health_check_interval_seconds: int = Field(default=300)
    max_videos_per_channel_fetch: int = Field(default=50)


config = AnalyticsConfig()
