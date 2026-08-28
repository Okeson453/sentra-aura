"""Rank/dedup unit tests — scoring features live in clipping-engine."""
from __future__ import annotations

from agent_runtime.agents.clipping.ai_clipping_agent.scoring import rank_and_dedup


def test_rank_prefers_higher_composite():
    cands = [
        {"clip_id": "a", "text": "low", "scores": {"composite": 0.2}},
        {"clip_id": "b", "text": "high curiosity gap why marine snow", "scores": {"composite": 0.9}},
    ]
    selected, rejected = rank_and_dedup(cands, max_clips=1, score_threshold=0.3)
    assert selected[0]["clip_id"] == "b"
    assert rejected


def test_dedup_rejects_near_duplicate():
    text = "marine snow sinks through the mesopelagic zone carrying carbon"
    cands = [
        {"clip_id": "a", "text": text, "scores": {"composite": 0.8}},
        {"clip_id": "b", "text": text + " today", "scores": {"composite": 0.75}},
    ]
    selected, rejected = rank_and_dedup(cands, max_clips=5, score_threshold=0.3)
    assert len(selected) == 1
    assert any(r.get("rejected_reason") == "duplicate_of_selected" for r in rejected)


def test_threshold_filters():
    cands = [{"clip_id": "x", "text": "mm", "scores": {"composite": 0.1}}]
    selected, rejected = rank_and_dedup(cands, max_clips=5, score_threshold=0.35)
    assert not selected
    assert rejected[0]["rejected_reason"] == "below_threshold"
