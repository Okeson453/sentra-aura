"""Configuration for the Agent Registry Service."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegistryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="agent-registry-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    metrics_port: int = Field(default=9090)


config = RegistryConfig()
