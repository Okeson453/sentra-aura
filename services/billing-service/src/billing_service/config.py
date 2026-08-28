"""Configuration for the Billing Service."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BillingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="billing-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    metrics_port: int = Field(default=9090)
    database_url: str = Field(default="postgresql+asyncpg://sentra:sentra@localhost:5432/billing")
    redis_url: str = Field(default="redis://localhost:6379/8")
    stripe_api_key: str = Field(default="")
    nats_url: str = Field(default="nats://localhost:4222")
    invoice_currency: str = Field(default="USD")
    invoice_due_days: int = Field(default=30)


config = BillingConfig()
