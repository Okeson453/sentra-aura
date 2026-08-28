"""Tests for the Policy Engine."""
from __future__ import annotations

from policy_engine.models import AutonomyLevel, RiskCategory, RiskScore, PolicyRule, PolicyEvaluation, RuleType
from policy_engine.engine import PolicyEngine
from policy_engine.store import PolicyStore


def test_risk_score_flagged():
    rs = RiskScore(category=RiskCategory.CONTENT, score=0.8, threshold=0.5)
    assert rs.score >= rs.threshold


def test_risk_score_not_flagged():
    rs = RiskScore(category=RiskCategory.CONTENT, score=0.3, threshold=0.5)
    assert rs.score < rs.threshold


def test_policy_engine_approve():
    engine = PolicyEngine()
    result = engine.evaluate("D1", "C1", AutonomyLevel.L2, {"risk": {"content": 0.2, "copyright": 0.1}})
    assert result.approved is True
    assert result.requires_human_override is False


def test_policy_engine_block():
    engine = PolicyEngine()
    result = engine.evaluate("D1", "C1", AutonomyLevel.L1, {"risk": {"content": 0.9, "copyright": 0.9}})
    assert result.approved is False
    assert result.requires_human_override is True


def test_policy_rule_block():
    rule = PolicyRule(rule_id="R1", name="Test Rule", rule_type=RuleType.EXACT, autonomy_level=AutonomyLevel.L1, action="BLOCK")
    engine = PolicyEngine([rule])
    result = engine.evaluate("D1", "C1", AutonomyLevel.L1, {})
    assert result.approved is False


def test_policy_store():
    store = PolicyStore()
    rule = PolicyRule(rule_id="R1", name="Test Rule", rule_type=RuleType.EXACT, autonomy_level=AutonomyLevel.L2)
    store.add("C1", rule)
    assert len(store.get("C1")) == 1
    store.clear("C1")
    assert len(store.get("C1")) == 0
