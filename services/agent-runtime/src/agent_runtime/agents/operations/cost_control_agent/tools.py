from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.cost_control_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def track_cost(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Budget tracking vs allocation with soft/hard alerts."""
    budget = payload.get("budget") or payload.get("content") or {}
    allocated = float(budget.get("allocated_usd") or budget.get("budget_usd") or 100.0)
    spent = float(budget.get("spent_usd") or 0.0)
    ratio = spent / allocated if allocated else 0.0
    alerts = []
    if ratio > 0.8:
        alerts.append({"level": "soft", "message": "80% budget consumed"})
    if ratio > 1.0:
        alerts.append({"level": "hard", "message": "budget exceeded"})
    return {"status": "ok", "tool": "track_cost", "allocated_usd": allocated, "spent_usd": spent,
            "utilization": round(ratio, 3), "alerts": alerts, "artifacts": alerts,
            "raw": f"topic={payload.get('topic','')} util={ratio:.2f}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
