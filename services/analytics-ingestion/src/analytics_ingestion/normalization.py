"""Metric normalization, signal processing, and composite score computation."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class NormalizedMetrics:
    video_id: str
    channel_id: str
    views: int
    normalized_ctr: float
    normalized_retention: float
    normalized_engagement: float
    normalized_watch_time: float
    composite_score: float
    confidence: float
    measured_at: datetime


def _coerce_datetime(value: Any) -> datetime:
    """Return ``value`` as a naive UTC datetime.

    Accepts a ``datetime``, an ISO-8601 string (with or without a trailing ``Z``,
    as produced by the REST surface), ``None`` (treated as now), or a POSIX
    timestamp.  ``measured_at`` arrives as a *string* over JSON, and the previous
    implementation performed ``datetime.now(timezone.utc) - <str>`` directly, raising
    ``TypeError`` and turning every /api/v1/normalize request into a 400.
    """
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            logger.warning("Unparseable measured_at %r; defaulting to utcnow()", value)
            return datetime.now(timezone.utc)
    else:
        logger.warning("Unsupported measured_at type %s; defaulting to utcnow()", type(value))
        return datetime.now(timezone.utc)

    # Keep a single naive-UTC representation: the rest of this module compares
    # against datetime.now(timezone.utc), which raises when mixed with aware datetimes.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def normalize_metrics(
    raw_metrics: dict[str, Any],
    channel_baseline: dict[str, float],
    category_baseline: dict[str, float] | None = None,
) -> NormalizedMetrics:
    """Normalize raw metrics against channel and category baselines.

    Applies:
    - Category baseline subtraction
    - Time-decay weighting (7-day half-life)
    - Channel baseline adjustment
    - Seasonal adjustment (placeholder)
    """
    video_id = raw_metrics["video_id"]
    channel_id = raw_metrics["channel_id"]
    views = raw_metrics.get("views", 0)
    ctr = raw_metrics.get("ctr", 0.0)
    avg_duration = raw_metrics.get("average_view_duration_seconds", 0.0)
    watch_time = raw_metrics.get("watch_time_seconds", 0)
    likes = raw_metrics.get("likes", 0)
    comments = raw_metrics.get("comments", 0)
    measured_at = _coerce_datetime(raw_metrics.get("measured_at"))

    # Channel baselines
    channel_avg_ctr = channel_baseline.get("avg_ctr", 0.05)
    channel_avg_duration = channel_baseline.get("avg_duration", 180.0)
    channel_avg_watch_time = channel_baseline.get("avg_watch_time", 300.0)

    # Category baselines (fallback to channel if not provided)
    if category_baseline is None:
        category_baseline = channel_baseline

    cat_avg_ctr = category_baseline.get("avg_ctr", channel_avg_ctr)
    cat_avg_duration = category_baseline.get("avg_duration", channel_avg_duration)

    # Normalize each metric relative to baselines
    norm_ctr = _safe_ratio(ctr, cat_avg_ctr)
    norm_duration = _safe_ratio(avg_duration, cat_avg_duration)
    norm_watch_time = _safe_ratio(watch_time, max(1, channel_avg_watch_time))

    # Engagement rate: (likes + comments) / views
    engagement = (likes + comments) / max(1, views)
    norm_engagement = _safe_ratio(engagement, channel_baseline.get("avg_engagement", 0.02))

    # Time-decay weighting
    age_days = (datetime.now(timezone.utc) - measured_at).total_seconds() / 86400
    decay_factor = math.exp(-age_days * math.log(2) / 7.0)  # 7-day half-life

    # Composite score (weighted sum)
    composite = (
        0.25 * norm_ctr
        + 0.25 * norm_duration
        + 0.20 * norm_watch_time
        + 0.20 * norm_engagement
        + 0.10 * decay_factor
    )

    # Confidence based on sample size
    confidence = min(1.0, math.sqrt(views) / 100.0)

    return NormalizedMetrics(
        video_id=video_id,
        channel_id=channel_id,
        views=views,
        normalized_ctr=round(norm_ctr, 4),
        normalized_retention=round(norm_duration, 4),
        normalized_engagement=round(norm_engagement, 4),
        normalized_watch_time=round(norm_watch_time, 4),
        composite_score=round(composite, 4),
        confidence=round(confidence, 4),
        measured_at=measured_at,
    )


def compute_performance_signal(
    metrics_history: list[NormalizedMetrics],
) -> dict[str, float]:
    """Compute trend signals from a time series of normalized metrics."""
    if len(metrics_history) < 2:
        return {"trend": 0.0, "volatility": 0.0, "momentum": 0.0}

    scores = np.array([m.composite_score for m in metrics_history])
    trend = np.polyfit(range(len(scores)), scores, 1)[0]
    volatility = float(np.std(scores))
    momentum = scores[-1] - scores[0] if len(scores) > 1 else 0.0

    return {
        "trend": round(float(trend), 4),
        "volatility": round(volatility, 4),
        "momentum": round(float(momentum), 4),
    }


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
