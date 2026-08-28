"""Unit tests for billing metering engine."""
from __future__ import annotations

from datetime import datetime, timedelta

from billing_service.metering import MeteringEngine


def test_record_usage():
    engine = MeteringEngine()
    record = engine.record_usage(
        tenant_id="tenant-1",
        channel_id="ch-1",
        service_name="agent-runtime",
        operation="llm_input_token",
        units=1000,
    )
    assert record.tenant_id == "tenant-1"
    assert record.operation == "llm_input_token"
    assert record.total_cost_usd > 0


def test_aggregate_by_tenant():
    engine = MeteringEngine()
    now = datetime.utcnow()
    engine.record_usage("tenant-1", "ch-1", "svc", "llm_input_token", 1000)
    engine.record_usage("tenant-1", "ch-1", "svc", "llm_output_token", 500)
    engine.record_usage("tenant-2", "ch-2", "svc", "llm_input_token", 2000)

    result = engine.aggregate_by_tenant("tenant-1", now - timedelta(hours=1), now + timedelta(hours=1))
    assert result["tenant_id"] == "tenant-1"
    assert result["total_cost_usd"] > 0
    assert "llm_input_token" in result["operations"]
    assert "llm_output_token" in result["operations"]


def test_aggregate_by_channel():
    engine = MeteringEngine()
    now = datetime.utcnow()
    engine.record_usage("tenant-1", "ch-1", "svc-a", "api_call", 100)
    engine.record_usage("tenant-1", "ch-1", "svc-b", "api_call", 200)

    result = engine.aggregate_by_channel("ch-1", now - timedelta(hours=1), now + timedelta(hours=1))
    assert result["channel_id"] == "ch-1"
    assert result["total_cost_usd"] > 0
    assert "svc-a" in result["by_service"]
    assert "svc-b" in result["by_service"]


def test_set_unit_cost():
    engine = MeteringEngine()
    engine.set_unit_cost("custom_op", 0.50)
    record = engine.record_usage("t1", "c1", "svc", "custom_op", 2)
    assert record.total_cost_usd == pytest.approx(1.0)


import pytest
