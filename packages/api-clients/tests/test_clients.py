"""Tests for generated API client stubs."""
from __future__ import annotations

import pytest

from api_clients.clients import AgentRegistryServiceClient
from api_clients.clients import AnalyticsIngestionClient
from api_clients.clients import BillingServiceClient
from api_clients.clients import ControlPlaneApiClient
from api_clients.clients import EventSchemaRegistryClient
from api_clients.clients import ModelEvalServiceClient
from api_clients.clients import NotificationServiceClient
from api_clients.clients import QuotaBrokerClient


@pytest.mark.asyncio
async def test_agent_registry_stub():
    client = AgentRegistryServiceClient(base_url="http://localhost:8000")
    # Stubs don't make real calls without a mock server
    assert client.base_url == "http://localhost:8000"
    await client.close()


@pytest.mark.asyncio
async def test_analytics_ingestion_stub():
    client = AnalyticsIngestionClient(base_url="http://localhost:8001")
    assert client.base_url == "http://localhost:8001"
    await client.close()


@pytest.mark.asyncio
async def test_billing_service_stub():
    client = BillingServiceClient(base_url="http://localhost:8002")
    assert client.base_url == "http://localhost:8002"
    await client.close()


@pytest.mark.asyncio
async def test_control_plane_stub():
    client = ControlPlaneApiClient(base_url="http://localhost:8003")
    assert client.base_url == "http://localhost:8003"
    await client.close()


@pytest.mark.asyncio
async def test_event_schema_registry_stub():
    client = EventSchemaRegistryClient(base_url="http://localhost:8004")
    assert client.base_url == "http://localhost:8004"
    await client.close()


@pytest.mark.asyncio
async def test_model_eval_service_stub():
    client = ModelEvalServiceClient(base_url="http://localhost:8005")
    assert client.base_url == "http://localhost:8005"
    await client.close()


@pytest.mark.asyncio
async def test_notification_service_stub():
    client = NotificationServiceClient(base_url="http://localhost:8006")
    assert client.base_url == "http://localhost:8006"
    await client.close()


@pytest.mark.asyncio
async def test_quota_broker_stub():
    client = QuotaBrokerClient(base_url="http://localhost:8007")
    assert client.base_url == "http://localhost:8007"
    await client.close()
