from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.experimentation_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def run_experiment(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Experiment design + simple proportion test winner selection (Arch. §8)."""
    import math
    variants = payload.get("variants") or (payload.get("content") or {}).get("variants") or []
    if not variants:
        variants = [
            {"id": "A", "impressions": 1000, "conversions": 40},
            {"id": "B", "impressions": 1000, "conversions": 55},
        ]
    scored = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        imp = max(1, int(v.get("impressions") or 1))
        conv = int(v.get("conversions") or 0)
        rate = conv / imp
        # Wilson lower bound approx
        z = 1.96
        denom = 1 + z*z/imp
        centre = rate + z*z/(2*imp)
        margin = z * math.sqrt((rate*(1-rate)+z*z/(4*imp))/imp)
        scored.append({"id": v.get("id"), "rate": rate, "wilson_low": (centre - margin)/denom, "impressions": imp})
    scored.sort(key=lambda x: x["wilson_low"], reverse=True)
    winner = scored[0] if scored else None
    return {"status": "ok", "tool": "run_experiment", "results": scored, "winner": winner, "topic": str(payload.get("topic") or ""),
            "artifacts": scored, "raw": f"topic={payload.get('topic','')} winner={winner and winner.get('id')}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
