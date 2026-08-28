"""Policy evaluation engine for SentraAura.

Supports rule types: exact, regex, range, semantic similarity,
composite (AND/OR/NOT), and temporal constraints.
Matches Architecture §9.2 and Backend Spec §9.
"""
from __future__ import annotations

import re
from typing import Any

from policy_engine.models import (
    AutonomyLevel,
    RiskCategory,
    RiskScore,
    PolicyRule,
    PolicyEvaluation,
    RuleType,
    CompositeOperator,
)


class PolicyEngine:
    """Evaluates policies against decisions with multi-type rule support."""

    RISK_WEIGHTS = {
        RiskCategory.CONTENT: 0.20,
        RiskCategory.COPYRIGHT: 0.20,
        RiskCategory.PLATFORM: 0.15,
        RiskCategory.BRAND: 0.15,
        RiskCategory.FINANCIAL: 0.10,
        RiskCategory.LEGAL: 0.15,
        RiskCategory.ETHICAL: 0.05,
    }

    AUTONOMY_THRESHOLDS = {
        AutonomyLevel.L0: 0.0,
        AutonomyLevel.L1: 0.3,
        AutonomyLevel.L2: 0.5,
        AutonomyLevel.L3: 0.7,
        AutonomyLevel.L4: 0.9,
    }

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self.rules = rules or []

    def evaluate(self, decision_id: str, channel_id: str, autonomy_level: AutonomyLevel, context: dict[str, Any]) -> PolicyEvaluation:
        """Evaluate a decision against all applicable policies."""
        risk_scores = self._calculate_risk_scores(context)
        overall_risk = self._compute_overall_risk(risk_scores)

        threshold = self.AUTONOMY_THRESHOLDS.get(autonomy_level, 0.5)
        approved = overall_risk < threshold
        requires_override = overall_risk >= threshold
        triggered_rules: list[str] = []

        # Check specific rules
        for rule in self.rules:
            if self._rule_applies(rule, autonomy_level, context):
                triggered = self._evaluate_rule(rule, context)
                if triggered:
                    triggered_rules.append(rule.rule_id)
                    if rule.action == "BLOCK":
                        approved = False
                        requires_override = True
                    elif rule.action == "REQUIRE_APPROVAL":
                        requires_override = True
                    elif rule.action == "WARN":
                        # Warn does not block but logs
                        pass
                    elif rule.action == "ESCALATE":
                        requires_override = True
                        autonomy_level = AutonomyLevel.L0

        return PolicyEvaluation(
            decision_id=decision_id,
            channel_id=channel_id,
            autonomy_level=autonomy_level,
            overall_risk=round(overall_risk, 4),
            risk_scores=risk_scores,
            approved=approved,
            requires_human_override=requires_override,
            policy_version=1,
            triggered_rules=triggered_rules,
        )

    def _rule_applies(self, rule: PolicyRule, autonomy_level: AutonomyLevel, context: dict[str, Any]) -> bool:
        """Check if a rule applies to this autonomy level and context."""
        if rule.autonomy_level and rule.autonomy_level != autonomy_level:
            return False
        if rule.channel_ids and context.get("channel_id") not in rule.channel_ids:
            return False
        if rule.tenant_ids and context.get("tenant_id") not in rule.tenant_ids:
            return False
        if rule.enabled is False:
            return False
        return True

    def _evaluate_rule(self, rule: PolicyRule, context: dict[str, Any]) -> bool:
        """Evaluate a single rule against context."""
        if rule.rule_type == RuleType.EXACT:
            return self._matches_exact(rule.condition, context)
        elif rule.rule_type == RuleType.REGEX:
            return self._matches_regex(rule.condition, context)
        elif rule.rule_type == RuleType.RANGE:
            return self._matches_range(rule.condition, context)
        elif rule.rule_type == RuleType.SEMANTIC:
            return self._matches_semantic(rule.condition, context)
        elif rule.rule_type == RuleType.COMPOSITE:
            return self._matches_composite(rule, context)
        elif rule.rule_type == RuleType.TEMPORAL:
            return self._matches_temporal(rule.condition, context)
        return self._matches_exact(rule.condition, context)

    def _matches_exact(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        for key, value in condition.items():
            if key not in context:
                return False
            if isinstance(value, dict) and "__in" in value:
                if context[key] not in value["__in"]:
                    return False
            elif context[key] != value:
                return False
        return True

    def _matches_regex(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        for key, pattern in condition.items():
            if key not in context:
                return False
            if not re.search(pattern, str(context[key])):
                return False
        return True

    def _matches_range(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        for key, range_spec in condition.items():
            if key not in context:
                return False
            val = context[key]
            if not isinstance(val, (int, float)):
                return False
            if "min" in range_spec and val < range_spec["min"]:
                return False
            if "max" in range_spec and val > range_spec["max"]:
                return False
        return True

    def _matches_semantic(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Semantic similarity matching using keyword overlap (placeholder for embedding model)."""
        threshold = condition.get("__threshold", 0.5)
        for key, target_phrases in condition.items():
            if key.startswith("__"):
                continue
            if key not in context:
                return False
            text = str(context[key]).lower()
            phrases = target_phrases if isinstance(target_phrases, list) else [target_phrases]
            matches = sum(1 for p in phrases if p.lower() in text)
            if matches / len(phrases) < threshold:
                return False
        return True

    def _matches_composite(self, rule: PolicyRule, context: dict[str, Any]) -> bool:
        """Evaluate composite rules with AND/OR/NOT operators."""
        operator = rule.composite_operator or CompositeOperator.AND
        sub_results = []
        for sub_condition in rule.sub_conditions or []:
            sub_results.append(self._matches_exact(sub_condition, context))
        if operator == CompositeOperator.AND:
            return all(sub_results)
        elif operator == CompositeOperator.OR:
            return any(sub_results)
        elif operator == CompositeOperator.NOT:
            return not any(sub_results)
        return all(sub_results)

    def _matches_temporal(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate temporal constraints (time windows, schedules)."""
        from datetime import datetime, time
        now = datetime.utcnow()
        if "allowed_hours" in condition:
            start_h, end_h = condition["allowed_hours"]
            if not (start_h <= now.hour <= end_h):
                return False
        if "blocked_days" in condition:
            if now.weekday() in condition["blocked_days"]:
                return False
        return True

    def _calculate_risk_scores(self, context: dict[str, Any]) -> list[RiskScore]:
        """Calculate risk scores from context."""
        scores = []
        for category in RiskCategory:
            raw_score = context.get("risk", {}).get(category.value.lower(), 0.0)
            threshold = context.get("thresholds", {}).get(category.value.lower(), 0.5)
            scores.append(RiskScore(category=category, score=raw_score, threshold=threshold))
        return scores

    def _compute_overall_risk(self, scores: list[RiskScore]) -> float:
        """Compute weighted overall risk with non-linear penalization."""
        total = 0.0
        total_weight = 0.0
        for score in scores:
            weight = self.RISK_WEIGHTS.get(score.category, 0.1)
            # Non-linear: high scores penalized more
            penalized = score.score ** (1 + score.score)
            total += penalized * weight
            total_weight += weight
        return total / total_weight if total_weight > 0 else 0.0
