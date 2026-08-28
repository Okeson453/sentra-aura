"""Agent-layer rank/dedup over clipping-engine scores (Architecture §6).

Composite ClipScore is owned by clipping-engine.pipeline.highlight_scoring.
This module only ranks, thresholds, and deduplicates scored candidates.
"""
from __future__ import annotations

from typing import Any


def rank_and_dedup(
    candidates: list[dict[str, Any]],
    *,
    max_clips: int = 5,
    score_threshold: float = 0.35,
    ngram_overlap: float = 0.55,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select top unique candidates by engine composite score."""

    def composite(c: dict[str, Any]) -> float:
        scores = c.get("scores") or {}
        if isinstance(scores, dict) and "composite" in scores:
            return float(scores["composite"])
        return float(c.get("composite") or c.get("score") or 0.0)

    ordered = sorted(candidates, key=composite, reverse=True)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_texts: list[set[str]] = []

    for c in ordered:
        score = composite(c)
        text = str(c.get("reconstructed_text") or c.get("text") or "").lower()
        tokens = set(text.split())
        if score < score_threshold:
            rejected.append({**c, "rejected_reason": "below_threshold"})
            continue
        dup = False
        for prev in seen_texts:
            if not tokens or not prev:
                continue
            overlap = len(tokens & prev) / max(1, len(tokens | prev))
            if overlap >= ngram_overlap:
                dup = True
                break
        if dup:
            rejected.append({**c, "rejected_reason": "duplicate_of_selected"})
            continue
        if len(selected) >= max_clips:
            rejected.append({**c, "rejected_reason": "max_clips"})
            continue
        rank = len(selected) + 1
        selected.append({**c, "rank": rank})
        seen_texts.append(tokens)

    return selected, rejected


# Backward-compatible aliases used by unit tests that still import scoring helpers
def composite_clip_score(features: dict[str, float]) -> float:
    """Legacy helper for unit tests — prefer engine scores in production path."""
    return float(features.get("composite") or 0.0)
