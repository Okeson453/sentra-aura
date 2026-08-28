from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.crisis_sentiment_anomaly_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def detect_anomaly(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Sentiment/volume anomaly detection with explicit thresholds."""
    # Thresholds (documented): volume z-score > 3.0 OR negative sentiment rate > 0.55 with n>=20
    VOLUME_Z = 3.0
    NEG_RATE = 0.55
    MIN_N = 20
    metrics = payload.get("metrics") or payload.get("content") or {}
    volume_z = float(metrics.get("volume_zscore") or metrics.get("volume_z") or 0.0)
    neg_rate = float(metrics.get("negative_rate") or 0.0)
    n = int(metrics.get("sample_size") or metrics.get("n") or 0)
    alerts = []
    if volume_z > VOLUME_Z:
        alerts.append({"type": "volume_spike", "value": volume_z, "threshold": VOLUME_Z, "severity": "high"})
    if neg_rate > NEG_RATE and n >= MIN_N:
        alerts.append({"type": "negative_sentiment", "value": neg_rate, "threshold": NEG_RATE, "n": n, "severity": "high"})
    return {"status": "ok", "tool": "detect_anomaly", "alerts": alerts, "thresholds": {"volume_z": VOLUME_Z, "neg_rate": NEG_RATE, "min_n": MIN_N},
            "artifacts": alerts, "raw": f"topic={payload.get('topic','')} alerts={len(alerts)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
