"""Tests for policy engine."""
from __future__ import annotations

import pytest
from datetime import datetime, time

from policy_engine.models import (
    AutonomyLevel, RiskCategory, RiskScore, PolicyRule, PolicyEvaluation,
    RuleType, CompositeOperator,
)
from policy_engine.engine import PolicyEngine
from policy_engine.ml_risk import MLEnsembleRiskScorer, AdaptiveThreshold


class TestPolicyEngine:
    def test_exact_rule_match(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r1", name="block_test", rule_type=RuleType.EXACT,
                condition={"action": "delete_channel"}, action="BLOCK",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "delete_channel"})
        assert result.approved is False
        assert "r1" in result.triggered_rules

    def test_exact_rule_no_match(self):
        engine = PolicyEngine(rules=[
            PolicyRule(rule_id="r1", name="block_test", condition={"action": "delete_channel"}, action="BLOCK"),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "publish_video"})
        assert result.approved is True
        assert result.triggered_rules == []

    def test_regex_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r2", name="block_urls", rule_type=RuleType.REGEX,
                condition={"content": r"https?://\S+"}, action="BLOCK",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"content": "Check out http://example.com"})
        assert result.approved is False
        assert "r2" in result.triggered_rules

    def test_range_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r3", name="budget_limit", rule_type=RuleType.RANGE,
                condition={"budget": {"min": 0, "max": 1000}}, action="REQUIRE_APPROVAL",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L3, {"budget": 500})
        assert result.requires_human_override is True
        assert "r3" in result.triggered_rules

    def test_range_rule_outside(self):
        engine = PolicyEngine(rules=[
            PolicyRule(rule_id="r3", name="budget_limit", rule_type=RuleType.RANGE, condition={"budget": {"min": 0, "max": 1000}}, action="REQUIRE_APPROVAL"),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L3, {"budget": 2000})
        assert result.requires_human_override is False
        assert result.triggered_rules == []

    def test_composite_and_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r4", name="composite", rule_type=RuleType.COMPOSITE,
                composite_operator=CompositeOperator.AND,
                sub_conditions=[{"action": "publish"}, {"platform": "youtube"}],
                action="BLOCK",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "publish", "platform": "youtube"})
        assert result.approved is False
        assert "r4" in result.triggered_rules

    def test_composite_or_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r5", name="or_rule", rule_type=RuleType.COMPOSITE,
                composite_operator=CompositeOperator.OR,
                sub_conditions=[{"action": "delete"}, {"action": "ban"}],
                action="BLOCK",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "ban"})
        assert result.approved is False
        assert "r5" in result.triggered_rules

    def test_temporal_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r6", name="business_hours", rule_type=RuleType.TEMPORAL,
                condition={"allowed_hours": [9, 17]}, action="BLOCK",
            ),
        ])
        # This test depends on current time; we just verify it doesn't crash
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "publish"})
        assert isinstance(result.approved, bool)

    def test_autonomy_level_thresholds(self):
        engine = PolicyEngine()
        # L0 should block anything with non-zero risk
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L0, {"risk": {"content": 0.1}})
        assert result.approved is False

        # L4 should allow low risk
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L4, {"risk": {"content": 0.1}})
        assert result.approved is True

    def test_overall_risk_computation(self):
        engine = PolicyEngine()
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {
            "risk": {cat.value.lower(): 0.5 for cat in RiskCategory},
            "thresholds": {cat.value.lower(): 0.5 for cat in RiskCategory},
        })
        assert 0 <= result.overall_risk <= 1
        assert len(result.risk_scores) == len(RiskCategory)

    def test_channel_filter(self):
        engine = PolicyEngine(rules=[
            PolicyRule(rule_id="r7", name="channel_specific", condition={"action": "delete"}, action="BLOCK", channel_ids=["ch-1"]),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "delete", "channel_id": "ch-1"})
        assert result.approved is False

        result = engine.evaluate("d1", "ch-2", AutonomyLevel.L2, {"action": "delete", "channel_id": "ch-2"})
        assert result.approved is True

    def test_disabled_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(rule_id="r8", name="disabled", condition={"action": "delete"}, action="BLOCK", enabled=False),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"action": "delete"})
        assert result.approved is True
        assert result.triggered_rules == []


class TestMLEnsembleRiskScorer:
    def test_ensemble_combines_scores(self):
        scorer = MLEnsembleRiskScorer(
            models=["content_safety", "copyright_risk"],
            weights={"content_safety": 0.6, "copyright_risk": 0.4},
        )
        result = scorer.score({"text": "test content", "metadata": {}})
        assert 0 <= result["ensemble_score"] <= 1
        assert "model_scores" in result

    def test_adaptive_threshold(self):
        threshold = AdaptiveThreshold(initial_threshold=0.5, min_threshold=0.1, max_threshold=0.9)
        threshold.update(0.3, False)  # False positive, lower threshold
        assert threshold.current < 0.5

        threshold2 = AdaptiveThreshold(initial_threshold=0.5)
        threshold2.update(0.8, True)  # False negative, raise threshold
        assert threshold2.current > 0.5

    def test_empty_context(self):
        scorer = MLEnsembleRiskScorer()
        result = scorer.score({})
        assert result["ensemble_score"] == 0.0


class TestPolicyEvaluationEdgeCases:
    def test_missing_risk_context(self):
        engine = PolicyEngine()
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {})
        assert result.overall_risk == 0.0
        assert result.approved is True

    def test_partial_risk_context(self):
        engine = PolicyEngine()
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"risk": {"content": 0.8}})
        assert result.overall_risk > 0
        assert len(result.risk_scores) == len(RiskCategory)

    def test_semantic_rule(self):
        engine = PolicyEngine(rules=[
            PolicyRule(
                rule_id="r9", name="semantic", rule_type=RuleType.SEMANTIC,
                condition={"content": ["spam", "scam"], "__threshold": 0.5},
                action="BLOCK",
            ),
        ])
        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"content": "This is a spam message"})
        assert result.approved is False

        result = engine.evaluate("d1", "ch-1", AutonomyLevel.L2, {"content": "Normal content"})
        assert result.approved is True
