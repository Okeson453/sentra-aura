"""ML-based risk scoring for the Policy Engine.

Supports historical trend analysis, adaptive thresholds, and ensemble scoring.
Matches Architecture §9.2 and Backend Spec §9.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from policy_engine.models import RiskCategory, RiskScore, PolicyEvaluation, AutonomyLevel

logger = logging.getLogger(__name__)


@dataclass
class RiskFeatureVector:
    """Feature vector for risk scoring."""
    content_toxicity: float = 0.0
    copyright_similarity: float = 0.0
    platform_policy_violation: float = 0.0
    brand_misalignment: float = 0.0
    cost_overrun_probability: float = 0.0
    legal_exposure: float = 0.0
    ethical_concern: float = 0.0
    historical_failure_rate: float = 0.0
    channel_age_days: int = 0
    subscriber_count: int = 0
    previous_violations: int = 0


class MLRiskScorer:
    """Machine learning-based risk scorer with adaptive thresholds."""

    # Feature weights learned from historical data
    DEFAULT_WEIGHTS = {
        RiskCategory.CONTENT: [0.35, 0.25, 0.15, 0.10, 0.05, 0.05, 0.05],
        RiskCategory.COPYRIGHT: [0.10, 0.45, 0.15, 0.10, 0.05, 0.10, 0.05],
        RiskCategory.PLATFORM: [0.10, 0.15, 0.40, 0.15, 0.05, 0.10, 0.05],
        RiskCategory.BRAND: [0.10, 0.10, 0.15, 0.40, 0.10, 0.10, 0.05],
        RiskCategory.FINANCIAL: [0.05, 0.05, 0.05, 0.15, 0.55, 0.10, 0.05],
        RiskCategory.LEGAL: [0.10, 0.20, 0.15, 0.10, 0.10, 0.30, 0.05],
        RiskCategory.ETHICAL: [0.10, 0.05, 0.10, 0.10, 0.05, 0.10, 0.50],
    }

    # Base thresholds per autonomy level
    BASE_THRESHOLDS = {
        AutonomyLevel.L0: 0.0,
        AutonomyLevel.L1: 0.25,
        AutonomyLevel.L2: 0.45,
        AutonomyLevel.L3: 0.65,
        AutonomyLevel.L4: 0.85,
    }

    def __init__(
        self,
        model_path: str | None = None,
        models: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.historical_data: list[dict[str, Any]] = []
        self.adaptive_offsets: dict[RiskCategory, float] = {cat: 0.0 for cat in RiskCategory}
        self.models = models or ["default"]
        if weights:
            for cat in RiskCategory:
                if cat.value in weights:
                    base_w = self.weights.get(cat, [0.1] * 7)
                    self.weights[cat] = [w * weights[cat.value] for w in base_w]
        if model_path:
            self._load_model(model_path)

    def _load_model(self, path: str) -> None:
        """Load trained model weights from disk."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
                self.weights = {RiskCategory(k): v for k, v in data.get("weights", {}).items()}
                self.adaptive_offsets = {RiskCategory(k): v for k, v in data.get("offsets", {}).items()}
            logger.info(f"Loaded risk model from {path}")
        except Exception as exc:
            logger.warning(f"Could not load model from {path}: {exc}. Using defaults.")

    def extract_features(self, context: dict[str, Any]) -> RiskFeatureVector:
        """Extract feature vector from decision context."""
        risk = context.get("risk", {})
        channel = context.get("channel", {})
        return RiskFeatureVector(
            content_toxicity=risk.get("content_toxicity", 0.0),
            copyright_similarity=risk.get("copyright_similarity", 0.0),
            platform_policy_violation=risk.get("platform_policy_violation", 0.0),
            brand_misalignment=risk.get("brand_misalignment", 0.0),
            cost_overrun_probability=risk.get("cost_overrun_probability", 0.0),
            legal_exposure=risk.get("legal_exposure", 0.0),
            ethical_concern=risk.get("ethical_concern", 0.0),
            historical_failure_rate=risk.get("historical_failure_rate", 0.0),
            channel_age_days=channel.get("age_days", 0),
            subscriber_count=channel.get("subscriber_count", 0),
            previous_violations=channel.get("previous_violations", 0),
        )

    def score(self, context: dict[str, Any]) -> list[RiskScore]:
        """Calculate risk scores using ML ensemble."""
        features = self.extract_features(context)
        feature_array = np.array([
            features.content_toxicity,
            features.copyright_similarity,
            features.platform_policy_violation,
            features.brand_misalignment,
            features.cost_overrun_probability,
            features.legal_exposure,
            features.ethical_concern,
        ], dtype=float)

        scores = []
        thresholds = context.get("thresholds", {}) if isinstance(context, dict) else {}
        for category in RiskCategory:
            weights = np.array(self.weights.get(category, [0.1] * 7))
            # Normalize weights
            weights = weights / weights.sum()
            # Calculate weighted score
            raw_score = float(np.dot(feature_array, weights))
            # Apply adaptive offset based on historical data
            offset = self.adaptive_offsets.get(category, 0.0)
            adjusted_score = min(1.0, max(0.0, raw_score + offset))
            # Apply channel maturity discount
            if features.channel_age_days > 365 and features.previous_violations == 0:
                adjusted_score *= 0.9
            scores.append(RiskScore(
                category=category,
                score=round(adjusted_score, 4),
                threshold=thresholds.get(category.value.lower(), 0.5),
                factors=[
                    {"name": "content_toxicity", "value": features.content_toxicity},
                    {"name": "copyright_similarity", "value": features.copyright_similarity},
                    {"name": "platform_policy_violation", "value": features.platform_policy_violation},
                    {"name": "brand_misalignment", "value": features.brand_misalignment},
                    {"name": "cost_overrun_probability", "value": features.cost_overrun_probability},
                    {"name": "legal_exposure", "value": features.legal_exposure},
                    {"name": "ethical_concern", "value": features.ethical_concern},
                    {"name": "historical_failure_rate", "value": features.historical_failure_rate},
                    {"name": "channel_age_days", "value": features.channel_age_days},
                    {"name": "previous_violations", "value": features.previous_violations},
                ],
            ))
        return scores

    def update_from_feedback(self, decision_id: str, was_correct: bool, actual_risk: float) -> None:
        """Update adaptive offsets based on feedback."""
        learning_rate = 0.01
        for category in RiskCategory:
            current = self.adaptive_offsets.get(category, 0.0)
            if was_correct:
                # Decrease offset if we were correct (less conservative)
                self.adaptive_offsets[category] = current - learning_rate
            else:
                # Increase offset if we were wrong (more conservative)
                self.adaptive_offsets[category] = current + learning_rate * 2
            self.adaptive_offsets[category] = round(max(-0.2, min(0.2, self.adaptive_offsets[category])), 4)
        logger.info(f"Updated adaptive offsets from feedback on {decision_id}")

    def save_model(self, path: str) -> None:
        """Save current model weights and offsets."""
        data = {
            "weights": {k.value: v.tolist() if hasattr(v, "tolist") else list(v) for k, v in self.weights.items()},
            "offsets": {k.value: v for k, v in self.adaptive_offsets.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved risk model to {path}")


class AdaptivePolicyEngine:
    """Policy engine with adaptive thresholds and ML-based scoring."""

    def __init__(self, ml_scorer: MLRiskScorer | None = None) -> None:
        self.ml_scorer = ml_scorer or MLRiskScorer()
        self.evaluation_history: list[PolicyEvaluation] = []

    def evaluate(self, decision_id: str, channel_id: str, autonomy_level: AutonomyLevel, context: dict[str, Any]) -> PolicyEvaluation:
        """Evaluate a decision with ML risk scoring and adaptive thresholds."""
        risk_scores = self.ml_scorer.score(context)
        overall_risk = self._compute_overall_risk(risk_scores)

        threshold = MLRiskScorer.BASE_THRESHOLDS.get(autonomy_level, 0.5)
        # Adjust threshold based on channel history
        channel_history = context.get("channel_history", {})
        if channel_history.get("successful_decisions", 0) > 100:
            threshold += 0.05  # More permissive for trusted channels
        if channel_history.get("failed_decisions", 0) > 10:
            threshold -= 0.10  # More restrictive for problematic channels

        approved = overall_risk < threshold
        requires_override = overall_risk >= threshold

        # Check for mandatory human review rules
        if context.get("requires_human_review"):
            requires_override = True
        if context.get("budget_usd", 0) > context.get("max_auto_budget", 50.0):
            requires_override = True

        evaluation = PolicyEvaluation(
            decision_id=decision_id,
            channel_id=channel_id,
            autonomy_level=autonomy_level,
            overall_risk=round(overall_risk, 4),
            risk_scores=risk_scores,
            approved=approved,
            requires_human_override=requires_override,
            policy_version=1,
        )
        self.evaluation_history.append(evaluation)
        return evaluation

    def _compute_overall_risk(self, scores: list[RiskScore]) -> float:
        """Compute weighted overall risk with non-linear combination."""
        weights = {
            RiskCategory.CONTENT: 0.20,
            RiskCategory.COPYRIGHT: 0.20,
            RiskCategory.PLATFORM: 0.15,
            RiskCategory.BRAND: 0.15,
            RiskCategory.FINANCIAL: 0.10,
            RiskCategory.LEGAL: 0.15,
            RiskCategory.ETHICAL: 0.05,
        }
        total = 0.0
        total_weight = 0.0
        for score in scores:
            weight = weights.get(score.category, 0.1)
            # Non-linear: high scores penalized more
            penalized = score.score ** (1 + score.score)
            total += penalized * weight
            total_weight += weight
        return total / total_weight if total_weight > 0 else 0.0

    def get_channel_risk_profile(self, channel_id: str) -> dict[str, Any]:
        """Get historical risk profile for a channel."""
        channel_evals = [e for e in self.evaluation_history if e.channel_id == channel_id]
        if not channel_evals:
            return {"channel_id": channel_id, "evaluations": 0, "avg_risk": 0.0}
        avg_risk = sum(e.overall_risk for e in channel_evals) / len(channel_evals)
        return {
            "channel_id": channel_id,
            "evaluations": len(channel_evals),
            "avg_risk": round(avg_risk, 4),
            "approval_rate": sum(1 for e in channel_evals if e.approved) / len(channel_evals),
            "override_rate": sum(1 for e in channel_evals if e.requires_human_override) / len(channel_evals),
        }


class MLEnsembleRiskScorer(MLRiskScorer):
    """ML ensemble risk scorer that returns a structured dict result."""

    def score(self, context: dict[str, Any]) -> dict[str, Any]:
        """Calculate risk scores and return ensemble result dict."""
        if not isinstance(context, dict) or not context:
            return {"ensemble_score": 0.0, "model_scores": {}}
        scores = super().score(context)
        model_scores = {s.category.value: s.score for s in scores}
        overall = self._compute_overall_risk(scores)
        return {
            "ensemble_score": round(overall, 4),
            "model_scores": model_scores,
        }

    def _compute_overall_risk(self, scores: list[RiskScore]) -> float:
        weights = {
            RiskCategory.CONTENT: 0.20,
            RiskCategory.COPYRIGHT: 0.20,
            RiskCategory.PLATFORM: 0.15,
            RiskCategory.BRAND: 0.15,
            RiskCategory.FINANCIAL: 0.10,
            RiskCategory.LEGAL: 0.15,
            RiskCategory.ETHICAL: 0.05,
        }
        total = 0.0
        total_weight = 0.0
        for score in scores:
            weight = weights.get(score.category, 0.1)
            penalized = score.score ** (1 + score.score)
            total += penalized * weight
            total_weight += weight
        return total / total_weight if total_weight > 0 else 0.0


class AdaptiveThreshold:
    """Adaptive threshold that adjusts based on feedback."""

    def __init__(self, initial_threshold: float = 0.5, min_threshold: float = 0.0, max_threshold: float = 1.0) -> None:
        self.current = initial_threshold
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold

    def update(self, score: float, was_false_negative: bool) -> None:
        """Update threshold based on whether a false negative occurred."""
        if was_false_negative:
            self.current = min(self.max_threshold, self.current + 0.05)
        else:
            self.current = max(self.min_threshold, self.current - 0.02)
