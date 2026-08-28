"""Routes for the Policy Engine."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from policy_engine.models import AutonomyLevel, PolicyEvaluation
from policy_engine.engine import PolicyEngine
from policy_engine.store import PolicyStore

router = APIRouter()

store = PolicyStore()


@router.post("/evaluate")
async def evaluate_policy(data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a decision against policies."""
    decision_id = data["decision_id"]
    channel_id = data["channel_id"]
    autonomy_level = AutonomyLevel(data.get("autonomy_level", "L1"))
    context = data.get("context", {})

    rules = store.get(channel_id)
    engine = PolicyEngine(rules)
    result = engine.evaluate(decision_id, channel_id, autonomy_level, context)

    return {
        "decision_id": result.decision_id,
        "channel_id": result.channel_id,
        "autonomy_level": result.autonomy_level.value,
        "overall_risk": result.overall_risk,
        "risk_scores": [
            {"category": rs.category.value, "score": rs.score, "flagged": rs.flagged}
            for rs in result.risk_scores
        ],
        "approved": result.approved,
        "requires_human_override": result.requires_human_override,
        "policy_version": result.policy_version,
    }


@router.post("/policies")
async def create_policy(data: dict[str, Any]) -> dict[str, Any]:
    """Create a policy rule."""
    rule = PolicyRule(
        rule_id=data["rule_id"],
        policy_type=data["policy_type"],
        autonomy_level=AutonomyLevel(data.get("autonomy_level", "L1")),
        condition=data.get("condition", {}),
        action=data.get("action", "ALLOW"),
        risk_threshold=data.get("risk_threshold", 0.5),
        requires_approval=data.get("requires_approval", False),
        approval_roles=data.get("approval_roles", []),
    )
    store.add(data["channel_id"], rule)
    return {"rule_id": rule.rule_id, "channel_id": data["channel_id"], "action": rule.action}


@router.get("/policies/{channel_id}")
async def list_policies(channel_id: str) -> list[dict[str, Any]]:
    """List policies for a channel."""
    rules = store.get(channel_id)
    return [
        {
            "rule_id": r.rule_id,
            "policy_type": r.policy_type,
            "autonomy_level": r.autonomy_level.value,
            "action": r.action,
            "requires_approval": r.requires_approval,
        }
        for r in rules
    ]
