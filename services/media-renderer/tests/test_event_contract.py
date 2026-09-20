"""Regression: published render events must satisfy their contract schema.

Audit finding (this cycle): ``_publish_video_rendered`` emitted
``event_type="video_rendered"`` with no ``event_id``/``timestamp``/
``script_id``/``video_id`` alignment, while
``contracts/events/v1/video_rendered.json`` requires ``event_id``,
``timestamp``, ``video_id``, ``script_id`` and restricts ``event_type`` to the
enum ``"video.rendered"``. The validator rejected every event, and the handler
then called ``publish_platform``, which bypasses validation — so render
completion events never reached consumers in contract-valid form.

These tests pin the payload to the schema.
"""
from __future__ import annotations

import pathlib

from event_bus.schema_validator import SchemaValidator

from media_renderer.worker import RenderWorker

SCHEMA = "video_rendered.json"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "contracts" / "events" / "v1" / SCHEMA


class _FakeJob:
    """Stand-in for RenderJobORM (only the attributes the builder reads)."""

    def __init__(self, **overrides):
        self.job_id = "render-abc123"
        self.project_id = "proj-1"
        self.channel_id = "chan-1"
        self.tenant_id = "tenant-1"
        self.output_url = "s3://bucket/out.mp4"
        self.resolution = "1080p"
        self.duration_seconds = 42
        self.render_plan = None
        self.metadata_json = None
        for key, value in overrides.items():
            setattr(self, key, value)


def _worker() -> RenderWorker:
    # __init__ probes nvidia-smi and builds an FFmpegWrapper; both are side-effect
    # free enough for the pure event builder, and the builder does no I/O.
    return RenderWorker()


def test_video_rendered_event_satisfies_published_schema() -> None:
    assert SCHEMA_PATH.exists(), f"missing contract schema at {SCHEMA_PATH}"
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))

    event = _worker()._build_video_rendered_event(_FakeJob())

    is_valid, errors = validator.validate(event, SCHEMA)
    assert is_valid, f"video_rendered payload violates its schema: {errors}"
    assert event["event_type"] == "video.rendered"
    assert event["video_id"] == "render-abc123"
    assert event["script_id"]


def test_pre_fix_payload_is_rejected_by_schema() -> None:
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))

    broken = {
        "event_type": "video_rendered",
        "job_id": "render-abc123",
        "channel_id": "chan-1",
        "tenant_id": "tenant-1",
        "output_url": "s3://bucket/out.mp4",
        "status": "completed",
    }
    is_valid, errors = validator.validate(broken, SCHEMA)
    assert not is_valid, "documented pre-fix payload unexpectedly validated"


def test_script_id_prefers_real_lineage_then_falls_back_to_project() -> None:
    worker = _worker()

    from_metadata = worker._build_video_rendered_event(
        _FakeJob(metadata_json={"script_id": "script-99"})
    )
    assert from_metadata["script_id"] == "script-99"

    from_plan = worker._build_video_rendered_event(
        _FakeJob(render_plan={"script_id": "script-77"})
    )
    assert from_plan["script_id"] == "script-77"

    no_lineage = worker._build_video_rendered_event(_FakeJob())
    assert no_lineage["script_id"] == "proj-1"


def test_optional_fields_only_emitted_when_real() -> None:
    worker = _worker()
    validator = SchemaValidator(schemas_dir=str(SCHEMA_PATH.parent))

    bare = worker._build_video_rendered_event(
        _FakeJob(output_url="", resolution="", duration_seconds=None)
    )
    assert "asset_urls" not in bare
    assert "resolution" not in bare
    assert "duration_seconds" not in bare
    is_valid, errors = validator.validate(bare, SCHEMA)
    assert is_valid, f"minimal payload must still validate: {errors}"

    full = worker._build_video_rendered_event(_FakeJob())
    assert full["asset_urls"] == {"output": "s3://bucket/out.mp4"}
    assert full["resolution"] == "1080p"
    assert full["duration_seconds"] == 42
    is_valid, errors = validator.validate(full, SCHEMA)
    assert is_valid, f"full payload must validate: {errors}"


def test_mock_mode_default_is_fail_safe() -> None:
    """The broker default must be REAL, not mock (see clipping-engine twin test).

    Audit finding: the default was ``"true"``, so production Helm (which set
    ``NATS_URL`` but not ``NATS_MOCK_MODE``) silently swallowed every
    ``video_rendered`` event into an in-process list.
    """
    source = pathlib.Path(__file__).resolve().parents[1] / "src" / "media_renderer" / "worker.py"
    text = source.read_text()
    assert '"NATS_MOCK_MODE", "false"' in text, (
        "media-renderer must default NATS_MOCK_MODE to false (fail-safe real broker)"
    )
    assert '"NATS_MOCK_MODE", "true"' not in text, "mock mode must not be the default"


def test_render_success_path_emits_the_event() -> None:
    """The completion path must actually publish, not merely define the builder.

    Audit finding: ``_publish_video_rendered`` existed but had no caller, so a
    successful render never emitted ``video.rendered`` at all — the event was
    dead code and no downstream stage could react to a finished render.
    """
    source = (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "media_renderer" / "worker.py"
    ).read_text()
    assert "await self._publish_video_rendered(job)" in source, (
        "_publish_video_rendered must be awaited on the render success path"
    )
