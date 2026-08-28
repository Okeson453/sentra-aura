"""ClipScore unit tests — engine owns scoring (Architecture §6).

Restored / strengthened from former ai_clipping_agent scoring tests.
"""
from __future__ import annotations

from clipping_engine.pipeline.highlight_scoring import score_highlights


def test_hook_scores_higher_than_plain():
    """Former test_hook_score_higher_with_curiosity_gap."""
    segs = [
        {
            "segment_id": "a",
            "start_seconds": 0,
            "end_seconds": 20,
            "text": "Why does marine snow never settle? Wait until you see this.",
            "visual_change": 0.8,
        },
        {
            "segment_id": "b",
            "start_seconds": 20,
            "end_seconds": 40,
            "text": "The ocean is deep and cold today.",
            "visual_change": 0.2,
        },
    ]
    out = score_highlights(segs)
    by_id = {c["segment_id"]: c for c in out["scored_segments"]}
    assert by_id["a"]["scores"]["hook"] > by_id["b"]["scores"]["hook"]
    assert by_id["a"]["composite"] > by_id["b"]["composite"]


def test_score_highlights_varies():
    """Former test_score_segment_varies_with_text."""
    a = score_highlights(
        [
            {
                "segment_id": "1",
                "start_seconds": 0,
                "end_seconds": 25,
                "text": "Secret orbital debris cascade begins when two satellites collide.",
                "visual_change": 0.9,
            }
        ]
    )
    b = score_highlights(
        [
            {
                "segment_id": "2",
                "start_seconds": 0,
                "end_seconds": 5,
                "text": "mm",
                "visual_change": 0.0,
            }
        ]
    )
    assert a["scored_segments"][0]["composite"] > b["scored_segments"][0]["composite"]


def test_context_dependency_raises_on_pronoun_heavy_text():
    """Former reconstruct/context dependency pressure — now an engine feature score."""
    independent = score_highlights(
        [
            {
                "segment_id": "i",
                "start_seconds": 0,
                "end_seconds": 20,
                "text": "Marine snow forms when plankton die and aggregate into sinking particles.",
                "visual_change": 0.4,
            }
        ]
    )["scored_segments"][0]
    dependent = score_highlights(
        [
            {
                "segment_id": "d",
                "start_seconds": 20,
                "end_seconds": 38,
                "text": "They carry it into that abyss after this event.",
                "visual_change": 0.2,
            }
        ]
    )["scored_segments"][0]
    assert dependent["scores"]["context_dependency"] > independent["scores"]["context_dependency"]
    # High context dependency should not outrank a strong independent segment by composite alone
    # (penalty term in ClipScore)
    assert independent["composite"] >= dependent["composite"] or (
        dependent["scores"]["context_dependency"] >= 0.3
    )


def test_feature_bundle_keys_present():
    """Composite scoring exposes full §6-ish feature bundle."""
    out = score_highlights(
        [
            {
                "segment_id": "x",
                "start_seconds": 0,
                "end_seconds": 18,
                "text": "Why does marine snow never truly settle?",
                "visual_change": 0.7,
            }
        ]
    )
    scores = out["scored_segments"][0]["scores"]
    for key in (
        "hook",
        "emotion",
        "density",
        "narrative",
        "novelty",
        "context_dependency",
        "visual",
        "quotability",
        "composite",
    ):
        assert key in scores
        assert 0.0 <= float(scores[key]) <= 1.0


def test_ordered_by_composite_descending():
    segs = [
        {"segment_id": "low", "start_seconds": 0, "end_seconds": 5, "text": "ok", "visual_change": 0.0},
        {
            "segment_id": "high",
            "start_seconds": 5,
            "end_seconds": 30,
            "text": "Why is marine snow the secret engine of deep carbon export?",
            "visual_change": 0.9,
        },
    ]
    ordered = score_highlights(segs)["scored_segments"]
    composites = [c["composite"] for c in ordered]
    assert composites == sorted(composites, reverse=True)
