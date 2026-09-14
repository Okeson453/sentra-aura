"""Regression tests for internal auth and Temporal worker registration."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import httpx
import jwt
import pytest
from pydantic import ValidationError

from orchestrator import activities
from orchestrator import client as temporal_client
from orchestrator import worker as worker_module
from orchestrator.config import Settings
from orchestrator.registry import ALL_ACTIVITIES, ALL_WORKFLOWS
from orchestrator.workflows import AgentWorkflow, LongFormVideoWorkflow


@pytest.mark.asyncio
async def test_service_call_sends_short_lived_service_credential(monkeypatch):
    seen: dict[str, object] = {}
    settings = SimpleNamespace(
        environment="production",
        jwt_secret="shared-service-secret-at-least-32-chars",
        service_name="orchestrator",
        service_auth_token_ttl_seconds=300,
        service_request_timeout_seconds=12.5,
        jwt_algorithm="HS256",
        api_key_header="X-API-Key",
    )

    class Response:
        content = b'{"ok": true}'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, bool]:
            return {"ok": True}

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            seen["timeout"] = kwargs["timeout"]
            seen["headers"] = kwargs["headers"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url, json=None):
            seen["url"] = url
            return Response()

    monkeypatch.setattr(activities, "get_settings", lambda: settings)
    monkeypatch.setattr(httpx, "AsyncClient", Client)

    assert await activities._call_service("media-renderer", "/render", {}) == {"ok": True}
    headers = seen["headers"]
    assert isinstance(headers, dict)
    authorization = headers["Authorization"]
    assert authorization.startswith("Bearer ")
    claims = jwt.decode(
        authorization.removeprefix("Bearer "),
        settings.jwt_secret,
        algorithms=["HS256"],
    )
    assert claims["sub"] == "service:orchestrator"
    assert claims["type"] == "service"
    assert headers["X-API-Key"] == settings.jwt_secret
    assert seen["timeout"].connect == 12.5


def test_non_local_settings_require_secure_service_signing_credential():
    with pytest.raises(ValidationError, match="JWT_SECRET must be a strong, unique value"):
        Settings(ENVIRONMENT="staging", JWT_SECRET="")


@pytest.mark.asyncio
async def test_temporal_client_uses_configured_host_and_namespace(monkeypatch):
    seen: dict[str, object] = {}
    expected = object()
    settings = SimpleNamespace(
        temporal_host="temporal.internal:7233",
        temporal_namespace="production-media",
    )

    async def connect(host, **kwargs):
        seen["host"] = host
        seen.update(kwargs)
        return expected

    monkeypatch.setattr(temporal_client, "get_settings", lambda: settings)
    monkeypatch.setattr(temporal_client.Client, "connect", connect)
    monkeypatch.setattr(temporal_client, "_temporal_client", None)

    assert await temporal_client.get_temporal_client() is expected
    assert seen == {"host": "temporal.internal:7233", "namespace": "production-media"}


@pytest.mark.asyncio
async def test_worker_uses_configured_task_queue_and_full_registries(monkeypatch):
    seen: dict[str, object] = {}
    client = object()
    settings = SimpleNamespace(temporal_task_queue="production-tasks")

    class Worker:
        def __init__(self, actual_client, **kwargs) -> None:
            seen["client"] = actual_client
            seen.update(kwargs)

        async def run(self) -> None:
            seen["ran"] = True

    async def get_client():
        return client

    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_temporal_client", get_client)
    monkeypatch.setattr(worker_module, "Worker", Worker)

    await worker_module.run_worker()
    assert seen == {
        "client": client,
        "task_queue": "production-tasks",
        "workflows": ALL_WORKFLOWS,
        "activities": ALL_ACTIVITIES,
        "ran": True,
    }


def test_registry_contains_all_workflows_and_referenced_activity_names():
    assert set(ALL_WORKFLOWS) == {AgentWorkflow, LongFormVideoWorkflow}
    registered_names = {
        activity.__temporal_activity_definition.name for activity in ALL_ACTIVITIES
    }
    tree = ast.parse(Path(temporal_client.__file__).with_name("workflows.py").read_text())
    referenced_names = {
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "execute_activity"
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    }
    assert referenced_names
    assert referenced_names <= registered_names
