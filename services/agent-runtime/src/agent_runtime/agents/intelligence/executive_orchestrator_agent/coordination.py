"""Inter-swarm coordination for the Executive Orchestrator (Architecture §4.2).

Builds agent assignments and a workflow DAG from strategy output plus optional
portfolio_plan / market_intelligence payloads (from peer intelligence agents).
Does not invoke those agents in-process — it consumes their structured outputs
when present on the request (AgentMessage payload), matching inter-swarm
contracts rather than deep intra-swarm handoffs.
"""
from __future__ import annotations

from typing import Any

from agent_runtime.agents.intelligence.executive_orchestrator_agent.schemas import (
    StrategyRequest,
)


def _top_trends(request: StrategyRequest, limit: int = 3) -> list[str]:
    topics: list[str] = []
    for sig in request.trend_signals or []:
        if isinstance(sig, dict):
            t = sig.get("topic") or sig.get("name") or sig.get("signal")
            if t:
                topics.append(str(t))
    mi = request.market_intelligence or {}
    for t in mi.get("top_topics") or mi.get("opportunities") or []:
        if isinstance(t, dict):
            topics.append(str(t.get("topic") or t.get("name") or t))
        else:
            topics.append(str(t))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:limit]


def build_agent_assignments(
    request: StrategyRequest,
    strategy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map strategy into inter-swarm agent assignments."""
    pillars = strategy.get("content_pillars") or ["General"]
    trends = _top_trends(request)
    focus = trends[0] if trends else (pillars[0] if pillars else "general content")

    assignments: list[dict[str, Any]] = [
        {
            "agent_id": "market_audience_intelligence_agent",
            "swarm": "intelligence",
            "task": "refresh_opportunity_signals",
            "priority": "high",
            "inputs_ref": ["channel_history", "resource_pool"],
            "depends_on": [],
        },
        {
            "agent_id": "portfolio_strategy_agent",
            "swarm": "intelligence",
            "task": "align_budget_and_topic_quotas",
            "priority": "high",
            "inputs_ref": ["portfolio_plan", "budget_remaining"],
            "depends_on": ["market_audience_intelligence_agent"],
        },
        {
            "agent_id": "research_agent",
            "swarm": "creative",
            "task": f"research_brief:{focus}",
            "priority": "normal",
            "inputs_ref": ["trend_signals", "audience_insights"],
            "depends_on": ["portfolio_strategy_agent"],
        },
        {
            "agent_id": "content_strategist_ideation_agent",
            "swarm": "creative",
            "task": f"ideate_from_pillars:{','.join(str(p) for p in pillars[:3])}",
            "priority": "normal",
            "inputs_ref": ["content_pillars"],
            "depends_on": ["research_agent"],
        },
        {
            "agent_id": "scripting_agent",
            "swarm": "creative",
            "task": "draft_scripts_for_schedule",
            "priority": "normal",
            "inputs_ref": ["publishing_schedule"],
            "depends_on": ["content_strategist_ideation_agent"],
        },
    ]

    # Portfolio plan may request extra distribution emphasis
    plan = request.portfolio_plan or {}
    if plan.get("emphasize_distribution") or (request.max_videos_per_week or 0) >= 5:
        assignments.append(
            {
                "agent_id": "publishing_agent",
                "swarm": "distribution",
                "task": "prepare_publication_pipeline",
                "priority": "normal",
                "inputs_ref": ["publishing_schedule"],
                "depends_on": ["scripting_agent"],
            }
        )

    return assignments


def build_workflow_dag(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn assignments into an explicit DAG of nodes."""
    nodes: list[dict[str, Any]] = []
    for i, a in enumerate(assignments):
        node_id = f"n{i+1}_{a['agent_id']}"
        deps = []
        for d in a.get("depends_on") or []:
            # map agent_id dependency to prior node ids
            for j, prev in enumerate(assignments):
                if prev["agent_id"] == d:
                    deps.append(f"n{j+1}_{prev['agent_id']}")
        nodes.append(
            {
                "node_id": node_id,
                "agent_id": a["agent_id"],
                "description": a.get("task", ""),
                "depends_on": deps,
            }
        )
    return nodes


def coordination_notes(request: StrategyRequest, strategy: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if request.portfolio_plan:
        notes.append("Incorporated portfolio_plan from portfolio_strategy_agent payload.")
    else:
        notes.append("No portfolio_plan provided; used request budget and cadence defaults.")
    if request.market_intelligence or request.trend_signals:
        notes.append("Incorporated market/trend signals for prioritization.")
    else:
        notes.append("No market_intelligence payload; strategy relies on channel inputs only.")
    notes.append(
        "Inter-swarm handoff: Intelligence → Creative (research/ideation/scripting); "
        "Orchestrator does not address intra-swarm steps individually."
    )
    if request.budget_remaining and request.budget_remaining < 100:
        notes.append("Budget remaining is low; resource_allocation should favor high-ROI stages.")
    return notes


def merge_strategy_from_provider(
    parsed: dict[str, Any] | None,
    request: StrategyRequest,
    raw_text: str,
) -> dict[str, Any]:
    """Normalize provider JSON (or free text) into strategy fields."""
    if parsed:
        return {
            "strategy_summary": str(
                parsed.get("strategy_summary")
                or parsed.get("summary")
                or raw_text[:400]
            ),
            "content_pillars": list(parsed.get("content_pillars") or []),
            "publishing_schedule": list(parsed.get("publishing_schedule") or []),
            "resource_allocation": dict(parsed.get("resource_allocation") or {}),
            "risk_mitigation": list(parsed.get("risk_mitigation") or []),
            "kpis": dict(parsed.get("kpis") or {}),
        }

    # Free-text path: still bind to input so output varies
    trends = _top_trends(request)
    pillar_seed = trends or ["Education", "Community"]
    return {
        "strategy_summary": (
            f"Strategy for {request.channel_name or 'channel'} over {request.planning_horizon}: "
            f"{raw_text[:300]}"
        ),
        "content_pillars": pillar_seed[:5],
        "publishing_schedule": [
            {
                "week": 1,
                "videos": [f"Focus: {pillar_seed[0]}"],
                "cadence": request.max_videos_per_week,
            }
        ],
        "resource_allocation": {
            "research": 0.2,
            "scripting": 0.3,
            "production": 0.35,
            "distribution": 0.15,
        },
        "risk_mitigation": ["Monitor retention weekly", "Respect brand_safety_level gates"],
        "kpis": {
            "max_videos_per_week": request.max_videos_per_week,
            "budget_remaining": request.budget_remaining,
        },
    }
