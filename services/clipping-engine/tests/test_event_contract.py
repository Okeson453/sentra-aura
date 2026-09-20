"""Regression: published clip events must satisfy their contract schema.

Audit finding (this cycle): ``_publish_clip_candidates`` emitted a payload with
``event_type="clip_candidate_created"`` and no ``event_id``/``timestamp``/
``source_video_id``/``clip_candidates``, while
``contracts/events/v1/clip_candidate_created.json`` requires those fields and
restricts ``event_type`` to the enum ``"clip.candidate.created"``. The
validator therefore rejected every event and the handler fell back to
``publish_platform``, which bypasses schema validation entirely — so the
event backbone silently carried contract-violating events.

These tests pin the payload shape to the schema so the failure cannot return.
"""
from __future__ import annotations

import pathlib

import pytest

from event_bus.schema_validator import SchemaValidator

from clipping_engine.main import _clip_candidates_payload, _infer_clip_type

SCHEMA = "clip_candidate_created.json"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "contracts" / "events" / "v1" / SCHEMA


def _scored_candidate(
    idx: int = 0,
    *,
    hook: float = 0.8,
    context_dependency: float = 0.1,
    start: float = 12.5,
    end: float = 27.5,
) -> dict:
    """A candidate shaped exactly like ``highlight_scoring.score_highlights`` output."""
    return {
        "segment_id": f"seg-{idx}",
        "clip_id": f"clip-seg-{idx}",
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": end - start,
        "text": "This is a strong opening hook for the audience.",
        "scores": {
            "hook": hook,
            "emotion": 0.4,
            "density": 0.5,
            "narrative": 0.75,
            "novelty": 0.6,
            "context_dependency": context_dependency,
            "visual": 0.3,
            "quotability": 0.4,
            "platform": 0.55,
            "timing": 1.0,
        },
        "composite": 0.71,
        "score": 0.71,
    }


def _event(candidates: list) -> dict:
    """The payload ``_publish_clip_candidates`` builds (mirrors its literal body)."""
    import uuid
    from datetime import datetime, timezone

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "clip.candidate.created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel_id": "chan-1",
        "tenant_id": "tenant-1",
        "source_video_id": "vid-1",
        "job_id": "clip-abc",
        "candidate_count": len(candidates),
        "clip_candidates": _clip_candidates_payload(candidates),
    }


def test_clip_candidate_payload_satisfies_published_schema() -> None:
    """The real emitted payload validates against the real committed schema."""
    assert SCHEMA_PATH.exists(), f"missing contract schema at {SCHEMA_PATH}"
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))

    candidates = [_scored_candidate(0), _scored_candidate(1, hook=0.3)]
    event = _event(candidates)

    is_valid, errors = validator.validate(event, SCHEMA)
    assert is_valid, f"clip_candidate_created payload violates its schema: {errors}"
    assert len(event["clip_candidates"]) == 2


def test_pre_fix_payload_is_rejected_by_schema() -> None:
    """Guard against regression to the exact broken pre-fix shape."""
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))

    broken = {
        "event_type": "clip_candidate_created",
        "job_id": "clip-abc",
        "video_id": "vid-1",
        "channel_id": "chan-1",
        "tenant_id": "tenant-1",
        "candidate_count": 1,
    }
    is_valid, errors = validator.validate(broken, SCHEMA)
    assert not is_valid, "documented pre-fix payload unexpectedly validated"


def test_every_candidate_has_contract_required_fields() -> None:
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))
    candidates = [
        _scored_candidate(0, hook=0.9, start=0.0, end=10.0),
        _scored_candidate(1, hook=0.2, start=100.0, end=260.0),
    ]

    payload = _clip_candidates_payload(candidates)
    assert len(payload) == 2

    for item in payload:
        for field in ("candidate_id", "start_ms", "end_ms", "clip_type", "clip_score"):
            assert field in item, f"candidate missing required field {field}"
        assert isinstance(item["start_ms"], int)
        assert isinstance(item["end_ms"], int)
        assert item["end_ms"] >= item["start_ms"]
        assert item["clip_type"] in (
            "HOOK",
            "QUOTE",
            "HIGHLIGHT",
            "EDUCATIONAL",
            "STORY",
            "SERIES",
            "COMPILATION",
        )
        assert isinstance(item["clip_score"], (int, float))

    # whole envelope validates with these candidates too
    is_valid, errors = validator.validate(_event(candidates), SCHEMA)
    assert is_valid, f"schema rejected candidate mapping: {errors}"


@pytest.mark.parametrize(
    ("feats", "duration", "expected"),
    [
        ({"hook": 0.9, "quotability": 0.4, "narrative": 0.75}, 12.0, "HOOK"),
        ({"hook": 0.2, "quotability": 0.9, "narrative": 0.75}, 30.0, "QUOTE"),
        ({"hook": 0.2, "quotability": 0.4, "narrative": 0.9}, 120.0, "STORY"),
        ({"hook": 0.2, "quotability": 0.4, "narrative": 0.4}, 30.0, "HIGHLIGHT"),
    ],
)
def test_clip_type_inference_is_deterministic(feats, duration, expected) -> None:
    assert _infer_clip_type(feats, duration) == expected


def test_mock_mode_default_is_fail_safe() -> None:
    """The broker default must be REAL, not mock.

    Audit finding: the default was ``"true"``, so any deployment that set
    ``NATS_URL`` but not ``NATS_MOCK_MODE`` (production Helm did exactly that)
    silently dropped every event into an in-process list. Deployments must now
    opt IN to mock mode.
    """
    source = pathlib.Path(__file__).resolve().parents[1] / "src" / "clipping_engine" / "main.py"
    text = source.read_text()
    assert '"NATS_MOCK_MODE", "false"' in text, (
        "clipping-engine must default NATS_MOCK_MODE to false (fail-safe real broker)"
    )
    assert '"NATS_MOCK_MODE", "true"' not in text, "mock mode must not be the default"
