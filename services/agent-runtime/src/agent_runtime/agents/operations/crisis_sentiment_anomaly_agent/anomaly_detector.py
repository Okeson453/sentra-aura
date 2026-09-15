"""Crisis / sentiment anomaly detection.

Combines explicit metrics (volume z-score, negative rate) with lightweight
lexical risk signals. Keyword-only scoring is insufficient for production (P1-03).
"""
from __future__ import annotations

import math
import re
from typing import Any

_RISK_TERMS: dict[str, float] = {
    "scandal": 0.9,
    "boycott": 0.95,
    "lawsuit": 0.85,
    "fraud": 0.9,
    "harassment": 0.8,
    "crisis": 0.7,
    "outrage": 0.75,
    "cancel": 0.65,
    "petition": 0.55,
    "controversy": 0.6,
    "misinformation": 0.7,
    "defamation": 0.8,
    "recall": 0.7,
    "investigation": 0.65,
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _lexical_risk(text: str) -> tuple[float, list[dict[str, Any]]]:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0, []
    hits: list[dict[str, Any]] = []
    score = 0.0
    for term, weight in _RISK_TERMS.items():
        count = sum(1 for t in tokens if t == term or t.startswith(term))
        if count:
            hits.append({"term": term, "count": count, "weight": weight})
            score += weight * min(count, 3) / 3.0
    density = min(1.0, len(hits) / max(1, math.log2(len(tokens) + 1)))
    combined = min(1.0, 0.7 * min(score, 1.5) / 1.5 + 0.3 * density)
    return combined, hits


def _metrics_risk(metrics: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    volume_z = float(metrics.get("volume_zscore") or metrics.get("volume_z") or 0.0)
    neg_rate = float(metrics.get("negative_rate") or metrics.get("neg_rate") or 0.0)
    n = int(metrics.get("sample_size") or metrics.get("n") or 0)
    signals: list[dict[str, Any]] = []
    score = 0.0
    if volume_z > 3.0:
        signals.append({"type": "volume_spike", "value": volume_z, "threshold": 3.0})
        score = max(score, min(1.0, (volume_z - 3.0) / 5.0 + 0.6))
    if neg_rate > 0.55 and n >= 20:
        signals.append({"type": "negative_sentiment", "value": neg_rate, "n": n, "threshold": 0.55})
        score = max(score, min(1.0, (neg_rate - 0.55) / 0.45 + 0.5))
    elif neg_rate > 0.4 and n >= 10:
        signals.append({"type": "elevated_negativity", "value": neg_rate, "n": n})
        score = max(score, 0.35)
    return score, signals


def detect_anomalies(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return composite anomaly score with explainable signals."""
    payload = payload or {}
    text_parts: list[str] = []
    for key in ("text", "comments", "body", "summary", "title"):
        val = payload.get(key)
        if isinstance(val, str):
            text_parts.append(val)
        elif isinstance(val, list):
            text_parts.extend(str(x) for x in val)
    text = " ".join(text_parts)

    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    lex_score, lex_hits = _lexical_risk(text)
    met_score, met_signals = _metrics_risk(metrics if isinstance(metrics, dict) else {})

    if met_signals:
        anomaly_score = min(1.0, 0.65 * met_score + 0.35 * lex_score)
    else:
        anomaly_score = lex_score

    signals = met_signals + [{"type": "lexical", "hits": lex_hits}] if lex_hits else list(met_signals)
    return {
        "anomaly_score": round(anomaly_score, 4),
        "flagged": anomaly_score > 0.5,
        "invoked": True,
        "signals": signals,
        "method": "metrics+lexicon",
    }
