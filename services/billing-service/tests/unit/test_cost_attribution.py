"""Unit tests for cost attribution logic."""
from __future__ import annotations

from datetime import datetime, timedelta

from billing_service.metering import MeteringEngine


def test_cost_attribution_by_service():
    engine = MeteringEngine()
    now = datetime.utcnow()

    # Simulate multi-service usage
    engine.record_usage("t1", "c1", "agent-runtime", "llm_input_token", 100000)
    engine.record_usage("t1", "c1", "agent-runtime", "llm_output_token", 50000)
    engine.record_usage("t1", "c1", "media-renderer", "video_render_minute", 120)
    engine.record_usage("t1", "c1", "clipping-engine", "api_call", 5000)
    engine.record_usage("t1", "c1", "asset-store", "storage_gb_month", 50)

    result = engine.aggregate_by_channel("c1", now - timedelta(hours=1), now + timedelta(hours=1))
    assert result["channel_id"] == "c1"
    assert result["total_cost_usd"] > 0
    assert "agent-runtime" in result["by_service"]
    assert "media-renderer" in result["by_service"]
    assert "clipping-engine" in result["by_service"]
    assert "asset-store" in result["by_service"]


def test_multi_tenant_isolation():
    engine = MeteringEngine()
    now = datetime.utcnow()

    engine.record_usage("tenant-a", "ch-a", "svc", "api_call", 1000)
    engine.record_usage("tenant-b", "ch-b", "svc", "api_call", 2000)

    result_a = engine.aggregate_by_tenant("tenant-a", now - timedelta(hours=1), now + timedelta(hours=1))
    result_b = engine.aggregate_by_tenant("tenant-b", now - timedelta(hours=1), now + timedelta(hours=1))

    assert result_a["total_cost_usd"] < result_b["total_cost_usd"]
    assert "tenant-a" == result_a["tenant_id"]
    assert "tenant-b" == result_b["tenant_id"]


def test_zero_usage_period():
    engine = MeteringEngine()
    now = datetime.utcnow()

    result = engine.aggregate_by_tenant("nonexistent", now - timedelta(days=1), now)
    assert result["total_cost_usd"] == 0.0
    assert result["operations"] == {}
