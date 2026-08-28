"""Integration tests for billing service API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from billing_service.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_record_usage():
    response = client.post(
        "/api/v1/meter",
        params={
            "tenant_id": "test-tenant",
            "channel_id": "test-channel",
            "service_name": "test-svc",
            "operation": "llm_input_token",
            "units": 1000,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recorded"] is True
    assert data["cost_usd"] > 0


def test_get_tenant_usage():
    client.post(
        "/api/v1/meter",
        params={
            "tenant_id": "usage-tenant",
            "channel_id": "ch-1",
            "service_name": "svc",
            "operation": "api_call",
            "units": 100,
        },
    )
    response = client.get("/api/v1/meter/tenant/usage-tenant")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "usage-tenant"
    assert data["total_cost_usd"] > 0


def test_create_and_get_invoice():
    response = client.post("/api/v1/invoices", params={"tenant_id": "inv-tenant", "days": 30})
    assert response.status_code == 200
    data = response.json()
    inv_id = data["invoice_id"]

    response = client.get(f"/api/v1/invoices/{inv_id}")
    assert response.status_code == 200
    assert response.json()["invoice_id"] == inv_id


def test_pay_invoice():
    response = client.post("/api/v1/invoices", params={"tenant_id": "pay-tenant", "days": 30})
    inv_id = response.json()["invoice_id"]

    response = client.post(f"/api/v1/invoices/{inv_id}/pay")
    assert response.status_code == 200
    assert response.json()["status"] == "paid"
