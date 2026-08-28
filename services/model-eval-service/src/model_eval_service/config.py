"""Configuration for the Model Evaluation Service."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelEvalConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    service_name: str = Field(default="model-eval-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    metrics_port: int = Field(default=9090)
    database_url: str = Field(default="postgresql+asyncpg://sentra:sentra@localhost:5432/model_eval")
    redis_url: str = Field(default="redis://localhost:6379/7")
    eval_dataset_path: str = Field(default="/data/evals")
    nats_url: str = Field(default="nats://localhost:4222")
    provider_gateway_url: str = Field(default="http://localhost:8000")
    min_eval_score_threshold: float = Field(default=0.75)
    drift_threshold: float = Field(default=0.05)
    safety_red_team_enabled: bool = Field(default=True)


config = ModelEvalConfig()
