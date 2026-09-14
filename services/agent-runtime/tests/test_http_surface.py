"""Regression tests for the agent-runtime HTTP surface.

Covers the production entrypoints the orchestrator dispatches to
(``/v1/execute``, ``/v1/draft-script``, ``/api/v1/invoke``). The governing
property under test: the runtime must fail LOUDLY. A broken dependency, an
unknown agent, or a missing approval must never be reported as success - that is
what previously let the autonomous loop appear to complete while doing nothing.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from agent_runtime.main import Settings, create_app

    # No live provider gateway is required: this suite asserts on the shape of
    # responses and on failure behaviour, not on a successful provider round-trip.
    app = create_app(Settings(require_auth=False))
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_full_agent_catalog(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"healthy", "degraded"}
    assert body["checks"]["catalog"]["agents_total"] >= 30


def test_agent_catalog_lists_every_agent(client: TestClient) -> None:
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) >= 30
    assert {"agent_type", "status"} <= set(agents[0])


def test_unknown_agent_type_is_rejected(client: TestClient) -> None:
    """An unknown agent is a 400 - never a silent success."""
    response = client.post(
        "/v1/execute", json={"agent_type": "not_a_real_agent", "task_type": "run"}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "HTTP_400"


def test_execute_requires_agent_and_task_fields(client: TestClient) -> None:
    response = client.post("/v1/execute", json={"agent_type": "scripting_agent"})
    assert response.status_code == 400


def test_publishing_requires_human_approval(client: TestClient) -> None:
    """Externally visible agents are gated by the runtime, not by the caller."""
    response = client.post(
        "/v1/execute",
        json={"agent_type": "publishing_agent", "task_type": "publish", "inputs": {}},
    )
    assert response.status_code == 403
    assert "approval" in response.json()["message"].lower()


def test_agent_failure_is_reported_not_swallowed(client: TestClient) -> None:
    """A dead provider gateway must surface as a failure, not as a fake success.

    The runtime is deliberately not pointed at a live gateway here, so the agent
    run must fail - and that failure must propagate as a non-2xx status.
    """
    response = client.post(
        "/v1/draft-script", json={"topic": "no gateway available", "research": {}}
    )
    assert response.status_code >= 400
    assert response.status_code != 200


def test_auth_required_rejects_missing_token() -> None:
    """With auth enabled the surface is fail-closed."""
    from agent_runtime.main import Settings, create_app

    app = create_app(
        Settings(require_auth=True, jwt_secret="unit-test-secret-0123456789abcdef")
    )
    with TestClient(app) as test_client:
        assert test_client.post("/v1/execute", json={}).status_code == 401


@pytest.mark.asyncio
async def test_checkpoint_round_trip(tmp_path) -> None:
    """Durable checkpoints persist and can be read back."""
    from agent_runtime.checkpoint_store import CheckpointStore, metadata

    store = CheckpointStore(f"sqlite+aiosqlite:///{tmp_path}/ckpt.db")
    async with store.engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    checkpoint_id = await store.save(
        agent_id="scripting_agent",
        phase="completed",
        cost_accrued_usd=0.12,
        tokens_consumed=42,
        payload={"task_type": "draft_script"},
    )
    latest = await store.latest("scripting_agent")
    assert latest is not None
    assert latest["checkpoint_id"] == checkpoint_id
    assert latest["phase"] == "completed"
    assert latest["payload"] == {"task_type": "draft_script"}
    await store.close()
