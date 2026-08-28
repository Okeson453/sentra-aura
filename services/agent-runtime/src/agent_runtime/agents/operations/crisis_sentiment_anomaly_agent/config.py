from __future__ import annotations
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRISIS_SENTIMENT_ANOMALY_AGENT_", extra="ignore")
    agent_name: str = "crisis_sentiment_anomaly_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(default_factory=lambda: os.environ.get("PROVIDER_GATEWAY_URL", "http://localhost:8081"))
    default_model: str = "mock-gpt-4"
