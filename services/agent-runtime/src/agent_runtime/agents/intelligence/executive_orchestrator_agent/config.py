"""Configuration for the Executive Orchestrator Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutiveOrchestratorConfig(BaseSettings):
    """Settings loaded from environment (prefix EXEC_ORCH_)."""

    model_config = SettingsConfigDict(env_prefix="EXEC_ORCH_", extra="ignore")

    agent_name: str = "executive_orchestrator_agent"
    max_retries: int = 3
    timeout_seconds: float = 120.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.4
    max_tokens: int = 2500
    default_planning_horizon: str = "30 days"
    default_max_videos_per_week: int = 3
