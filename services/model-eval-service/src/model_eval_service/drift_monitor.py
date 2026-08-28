"""Model drift detection using statistical tests and embedding distance."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    agent_id: str
    version: str
    drift_detected: bool
    drift_score: float
    drift_type: str
    baseline_window: str
    current_window: str
    feature_drifts: dict[str, float]
    recommended_action: str
    reported_at: datetime


class DriftMonitor:
    """Monitors model output distributions for drift."""

    def __init__(self, drift_threshold: float = 0.05) -> None:
        self.drift_threshold = drift_threshold
        self._baselines: dict[str, dict[str, Any]] = {}  # agent_id:version -> baseline stats

    def set_baseline(
        self,
        agent_id: str,
        version: str,
        scores: list[float],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Set the baseline distribution for an agent version."""
        key = f"{agent_id}:{version}"
        self._baselines[key] = {
            "scores": np.array(scores),
            "mean": float(np.mean(scores)),
            "std": float(np.std(scores)),
            "embeddings": np.array(embeddings) if embeddings else None,
            "set_at": datetime.utcnow(),
        }
        logger.info("Baseline set for %s: mean=%.4f, std=%.4f", key, self._baselines[key]["mean"], self._baselines[key]["std"])

    def detect_drift(
        self,
        agent_id: str,
        version: str,
        current_scores: list[float],
        current_embeddings: list[list[float]] | None = None,
    ) -> DriftReport:
        """Detect drift between baseline and current distributions."""
        key = f"{agent_id}:{version}"
        baseline = self._baselines.get(key)
        if not baseline:
            raise ValueError(f"No baseline set for {key}")

        baseline_scores = baseline["scores"]
        current_scores_arr = np.array(current_scores)

        # KS test for distribution shift
        ks_stat, ks_pvalue = stats.ks_2samp(baseline_scores, current_scores_arr)

        # Welch's t-test for mean shift
        t_stat, t_pvalue = stats.ttest_ind(baseline_scores, current_scores_arr, equal_var=False)

        # Effect size (Cohen's d)
        pooled_std = np.sqrt((np.std(baseline_scores)**2 + np.std(current_scores_arr)**2) / 2)
        cohens_d = abs(np.mean(baseline_scores) - np.mean(current_scores_arr)) / max(pooled_std, 1e-9)

        # Embedding drift (cosine distance)
        embedding_drift = 0.0
        if current_embeddings is not None and baseline["embeddings"] is not None:
            embedding_drift = self._compute_embedding_drift(baseline["embeddings"], np.array(current_embeddings))

        # Composite drift score
        drift_score = max(1.0 - ks_pvalue, cohens_d * 0.5, embedding_drift)
        drift_detected = drift_score > self.drift_threshold

        feature_drifts = {
            "ks_pvalue": round(float(ks_pvalue), 4),
            "t_pvalue": round(float(t_pvalue), 4),
            "cohens_d": round(float(cohens_d), 4),
            "embedding_drift": round(float(embedding_drift), 4),
        }

        recommended_action = "none"
        if drift_detected:
            if cohens_d > 0.8:
                recommended_action = "rollback"
            elif ks_pvalue < 0.01:
                recommended_action = "retrain"
            else:
                recommended_action = "investigate"

        return DriftReport(
            agent_id=agent_id,
            version=version,
            drift_detected=drift_detected,
            drift_score=round(float(drift_score), 4),
            drift_type="statistical" if embedding_drift < 0.1 else "embedding",
            baseline_window=baseline["set_at"].isoformat(),
            current_window=datetime.utcnow().isoformat(),
            feature_drifts=feature_drifts,
            recommended_action=recommended_action,
            reported_at=datetime.utcnow(),
        )

    def _compute_embedding_drift(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
    ) -> float:
        """Compute average cosine distance between baseline and current embedding centroids."""
        baseline_centroid = np.mean(baseline, axis=0)
        current_centroid = np.mean(current, axis=0)
        cos_sim = np.dot(baseline_centroid, current_centroid) / (
            np.linalg.norm(baseline_centroid) * np.linalg.norm(current_centroid) + 1e-9
        )
        return float(1.0 - cos_sim)
