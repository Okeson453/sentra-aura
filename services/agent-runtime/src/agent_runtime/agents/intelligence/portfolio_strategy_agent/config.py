"""Configuration for Portfolio Strategy Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortfolioStrategyConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PSA_", extra="ignore")

    agent_name: str = "portfolio_strategy_agent"
    timeout_seconds: float = 90.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.35
    max_tokens: int = 2200
    max_budget_share: float = 0.40
