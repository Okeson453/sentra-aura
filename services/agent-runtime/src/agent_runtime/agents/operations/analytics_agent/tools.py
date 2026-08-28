from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.analytics_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def analyze_metrics(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Analyze performance metrics from analytics-ingestion shaped payloads."""
    rows = payload.get("metrics") or payload.get("content") or payload.get("rows") or []
    if isinstance(rows, dict):
        rows = rows.get("rows") or [rows]
    views = ctr = eng = 0.0
    n = 0
    for r in (rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            continue
        views += float(r.get("views") or r.get("view_count") or 0)
        ctr += float(r.get("ctr") or 0)
        eng += float(r.get("engagement_rate") or r.get("engagement") or 0)
        n += 1
    summary = {
        "videos": n,
        "total_views": views,
        "avg_ctr": (ctr / n) if n else 0.0,
        "avg_engagement": (eng / n) if n else 0.0,
    }
    return {"status": "ok", "tool": "analyze_metrics", "summary": summary,
            "artifacts": [summary], "raw": f"topic={payload.get('topic','')} videos={n} views={views}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
