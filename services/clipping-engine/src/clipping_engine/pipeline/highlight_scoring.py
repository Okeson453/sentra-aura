"""Highlight scoring pipeline stage — Architecture §6 ClipScore (service-owned)."""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_HOOK = re.compile(r"\b(why|how|secret|never|shocking|actually|wait)\b|\?", re.I)
_PRONOUN = re.compile(r"\b(it|they|this|that|these|those|he|she)\b", re.I)


def _features(seg: dict[str, Any]) -> dict[str, float]:
    text = str(seg.get("text") or "")
    words = text.split()
    dur = max(0.1, float(seg.get("end_seconds") or 0) - float(seg.get("start_seconds") or 0))
    hook = 0.85 if _HOOK.search(text[:80] or "") else 0.35
    emotion = 0.7 if any(w in text.lower() for w in ("fail", "win", "shock", "love", "fear")) else 0.4
    density = min(1.0, len(set(w.lower() for w in words)) / max(1, len(words)) + 0.2)
    novelty = 0.6
    narrative = 0.75 if len(words) >= 12 else 0.4
    context_dep = min(1.0, len(_PRONOUN.findall(text)) / max(1, len(words)) * 3)
    visual = float(seg.get("visual_change") or 0.3)
    quotability = 0.7 if len(words) < 40 and hook > 0.5 else 0.4
    platform = 0.55
    timing = 1.0 if 8 <= dur <= 45 else 0.5
    composite = (
        0.12 * hook + 0.1 * emotion + 0.1 * density + 0.12 * narrative
        + 0.1 * novelty + 0.08 * visual + 0.08 * quotability + 0.08 * platform
        + 0.07 * timing - 0.15 * context_dep
    )
    composite = max(0.0, min(1.0, composite))
    return {
        "hook": round(hook, 3),
        "emotion": round(emotion, 3),
        "density": round(density, 3),
        "narrative": round(narrative, 3),
        "novelty": round(novelty, 3),
        "context_dependency": round(context_dep, 3),
        "visual": round(visual, 3),
        "quotability": round(quotability, 3),
        "platform": round(platform, 3),
        "timing": round(timing, 3),
        "composite": round(composite, 3),
    }


def score_highlights(
    segments: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score candidate segments — engine owns ClipScore (Architecture §6)."""
    scored_segments: list[dict[str, Any]] = []
    for seg in segments:
        feats = _features(seg)
        start = float(seg.get("start_seconds") or 0)
        end = float(seg.get("end_seconds") or start + 15)
        scored_segments.append({
            **seg,
            "clip_id": f"clip-{seg.get('segment_id', 'x')}",
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": max(0.0, end - start),
            "scores": feats,
            "composite": feats["composite"],
            "score": feats["composite"],
            "context_complete": feats["context_dependency"] < 0.35,
        })
    scored_segments.sort(key=lambda c: c["composite"], reverse=True)
    logger.info("scored %d segments", len(scored_segments))
    return {
        "scored_segments": scored_segments,
        "candidates": scored_segments,
        "count": len(scored_segments),
    }
