"""Configuration for Market & Audience Intelligence Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketAudienceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAI_", extra="ignore")

    agent_name: str = "market_audience_intelligence_agent"
    timeout_seconds: float = 60.0
    data_ingestion_url: str = Field(
        default_factory=lambda: os.environ.get(
            "DATA_INGESTION_PIPELINE_URL", "http://localhost:8010"
        )
    )
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000
