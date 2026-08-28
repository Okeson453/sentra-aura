"""Consolidated inter-service API clients (one module; thin per-package re-exports)."""
from __future__ import annotations

from typing import Any

import httpx


class BaseServiceClient:
    """Shared async HTTP client helpers."""

    service_name: str = "service"

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health(self) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def ready(self) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/ready")
        response.raise_for_status()
        return response.json()


class DataIngestionPipelineClient(BaseServiceClient):
    """Typed HTTP client for data-ingestion-pipeline."""

    service_name = "data-ingestion-pipeline"

    async def ingest_youtube(self, data: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(f"{self.base_url}/ingest/youtube", json=data)
        response.raise_for_status()
        return response.json()

    async def ingest_trends(self, data: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(f"{self.base_url}/ingest/trends", json=data)
        response.raise_for_status()
        return response.json()

    async def ingest_competitors(self, data: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(f"{self.base_url}/ingest/competitors", json=data)
        response.raise_for_status()
        return response.json()

class AgentRegistryServiceClient(BaseServiceClient):
    """Async HTTP client for agent-registry-service."""

    service_name = "agent-registry-service"

class AgentRuntimeClient(BaseServiceClient):
    """Async HTTP client for agent-runtime."""

    service_name = "agent-runtime"

class AnalyticsIngestionClient(BaseServiceClient):
    """Async HTTP client for analytics-ingestion."""

    service_name = "analytics-ingestion"

class AssetStoreClient(BaseServiceClient):
    """Async HTTP client for asset-store."""

    service_name = "asset-store"

class BillingServiceClient(BaseServiceClient):
    """Async HTTP client for billing-service."""

    service_name = "billing-service"

class ClippingEngineClient(BaseServiceClient):
    """Async HTTP client for clipping-engine."""

    service_name = "clipping-engine"

class ContentGraphServiceClient(BaseServiceClient):
    """Async HTTP client for content-graph-service."""

    service_name = "content-graph-service"

class ControlPlaneApiClient(BaseServiceClient):
    """Async HTTP client for control-plane-api."""

    service_name = "control-plane-api"

class EventSchemaRegistryClient(BaseServiceClient):
    """Async HTTP client for event-schema-registry."""

    service_name = "event-schema-registry"

class MediaRendererClient(BaseServiceClient):
    """Async HTTP client for media-renderer."""

    service_name = "media-renderer"

class ModelEvalServiceClient(BaseServiceClient):
    """Async HTTP client for model-eval-service."""

    service_name = "model-eval-service"

class NotificationServiceClient(BaseServiceClient):
    """Async HTTP client for notification-service."""

    service_name = "notification-service"

class OrchestratorClient(BaseServiceClient):
    """Async HTTP client for orchestrator."""

    service_name = "orchestrator"

class PolicyEngineClient(BaseServiceClient):
    """Async HTTP client for policy-engine."""

    service_name = "policy-engine"

class ProviderGatewayClient(BaseServiceClient):
    """Async HTTP client for provider-gateway."""

    service_name = "provider-gateway"

class PublishingServiceClient(BaseServiceClient):
    """Async HTTP client for publishing-service."""

    service_name = "publishing-service"

class QuotaBrokerClient(BaseServiceClient):
    """Async HTTP client for quota-broker."""

    service_name = "quota-broker"

class ResearchServiceClient(BaseServiceClient):
    """Async HTTP client for research-service."""

    service_name = "research-service"

class RightsRegistryServiceClient(BaseServiceClient):
    """Async HTTP client for rights-registry-service."""

    service_name = "rights-registry-service"

