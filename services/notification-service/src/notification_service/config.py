"""Configuration for the Notification Service."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="notification-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    metrics_port: int = Field(default=9090)
    database_url: str = Field(default="postgresql+asyncpg://sentra:sentra@localhost:5432/notification_service")
    redis_url: str = Field(default="redis://localhost:6379/5")
    slack_webhook_url: str = Field(default="")
    pagerduty_service_key: str = Field(default="")
    smtp_host: str = Field(default="smtp.example.com")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    nats_url: str = Field(default="nats://localhost:4222")
    dedup_window_seconds: int = Field(default=300)
    rate_limit_per_minute: int = Field(default=100)


config = NotificationConfig()
