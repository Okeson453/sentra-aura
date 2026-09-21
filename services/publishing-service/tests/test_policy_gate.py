"""Regression tests for the governance gate on the publishing path.

Architecture §9 requires that no content reaches an external platform without a
policy decision. Before the gate existed ``publishing-service`` had zero
references to ``policy-engine``: the orchestrator evaluated policy *after*
``publish_content`` had already uploaded, so a restrictive, absent or failed
policy could not prevent a publication.

These tests pin the three guarantees that make the gate real:

* an explicit denial blocks the publish and the adapter is never called;
* an unevaluable gate (unreachable / erroring policy-engine) fails closed;
* an explicit approval lets the publish proceed to the adapter.

Each case asserts the terminal state actually persisted, so a fix that merely
raised without recording the block would still fail here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from publishing_service import main
from publishing_service import policy_gate


def _seed(engine, *, platforms=None):
    """Create a publication + queued job and return both ids."""
    session = sessionmaker(bind=engine)()
    suffix = uuid.uuid4().hex
    publication = main.Publication(
        publication_id=f"pub-{suffix[:12]}",
        tenant_id="tenant-gate",
        channel_id="channel-gate",
        title="gate-title",
        description="gate-description",
        status="queued",
        asset_id="video.mp4",
        platforms=platforms or ["youtube"],
        tags=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    job = main.PublishJob(
        job_id=f"publish-{suffix[:12]}",
        publication_id=publication.publication_id,
        status="queued",
        platform_results=[],
        started_at=datetime.now(timezone.utc),
    )
    session.add_all([publication, job])
    session.commit()
    # Capture the ids before closing: ``commit`` expires the instances, so
    # reading them afterwards would raise DetachedInstanceError.
    job_id = job.job_id
    publication_id = publication.publication_id
    session.close()
    return job_id, publication_id


@pytest.mark.asyncio
async def test_policy_denial_blocks_publish_and_adapter_is_never_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core guarantee: a governance denial stops the upload."""
    engine = create_engine(main.config.database_url)
    job_id, publication_id = _seed(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))

    adapter_calls: list[str] = []

    async def spy_publish(platform_id: str, pub) -> dict[str, object]:
        adapter_calls.append(platform_id)
        return {"platform": platform_id, "status": "uploaded", "video_id": "real-id"}

    async def denied(**kwargs) -> dict[str, object]:
        raise policy_gate.PolicyDenied("risk 0.9 exceeds threshold 0.3")

    monkeypatch.setattr(main, "_publish_to_platform", spy_publish)
    monkeypatch.setattr(policy_gate, "require_publish_approval", denied)

    session = sessionmaker(bind=engine)()
    try:
        await main._process_publish_job(job_id, publication_id)
        job = session.query(main.PublishJob).filter(main.PublishJob.job_id == job_id).first()
        pub = (
            session.query(main.Publication)
            .filter(main.Publication.publication_id == publication_id)
            .first()
        )
        assert adapter_calls == [], "adapter was called despite a governance denial"
        assert job.status == "failed"
        assert pub.status == "failed"
        assert pub.status != "published"
        assert "policy gate blocked publication" in (job.error_message or "")
        assert job.platform_results == []
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_unreachable_policy_engine_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unevaluable gate is a denial, never an implicit allow."""
    engine = create_engine(main.config.database_url)
    job_id, publication_id = _seed(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))

    adapter_calls: list[str] = []

    async def spy_publish(platform_id: str, pub) -> dict[str, object]:
        adapter_calls.append(platform_id)
        return {"platform": platform_id, "status": "uploaded", "video_id": "real-id"}

    async def unreachable(**kwargs) -> dict[str, object]:
        raise RuntimeError("policy gate unreachable: connection refused")

    monkeypatch.setattr(main, "_publish_to_platform", spy_publish)
    monkeypatch.setattr(policy_gate, "require_publish_approval", unreachable)

    session = sessionmaker(bind=engine)()
    try:
        await main._process_publish_job(job_id, publication_id)
        job = session.query(main.PublishJob).filter(main.PublishJob.job_id == job_id).first()
        pub = (
            session.query(main.Publication)
            .filter(main.Publication.publication_id == publication_id)
            .first()
        )
        assert adapter_calls == [], "adapter was called with an unevaluable gate"
        assert job.status == "failed"
        assert pub.status == "failed"
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_approval_lets_the_publish_proceed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A positive control: an approved decision must not become a new blocker."""
    engine = create_engine(main.config.database_url)
    job_id, publication_id = _seed(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))

    adapter_calls: list[str] = []

    async def spy_publish(platform_id: str, pub) -> dict[str, object]:
        adapter_calls.append(platform_id)
        return {
            "platform": platform_id,
            "status": "uploaded",
            "video_id": "real-id",
            "url": "https://www.youtube.com/watch?v=real-id",
        }

    async def approved(**kwargs) -> dict[str, object]:
        return {"approved": True, "overall_risk": 0.1, "policy_version": 1}

    monkeypatch.setattr(main, "_publish_to_platform", spy_publish)
    monkeypatch.setattr(policy_gate, "require_publish_approval", approved)
    monkeypatch.setattr(main, "publish_publication_published", _noop_emit)

    session = sessionmaker(bind=engine)()
    try:
        await main._process_publish_job(job_id, publication_id)
        job = session.query(main.PublishJob).filter(main.PublishJob.job_id == job_id).first()
        pub = (
            session.query(main.Publication)
            .filter(main.Publication.publication_id == publication_id)
            .first()
        )
        assert adapter_calls == ["youtube"], "an approved publish did not reach the adapter"
        assert job.status == "completed"
        assert pub.status == "published"
        assert job.gate_decision == {"approved": True, "overall_risk": 0.1, "policy_version": 1}
    finally:
        session.close()
        engine.dispose()


async def _noop_emit(publication, platform_results) -> int:
    return 0


def test_gate_is_enabled_by_default() -> None:
    """Fail-closed default: an unconfigured deployment still enforces the gate."""
    assert policy_gate.policy_gate_enabled() is True


def test_gate_can_only_be_disabled_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_GATE_ENABLED", "false")
    assert policy_gate.policy_gate_enabled() is False
    monkeypatch.setenv("POLICY_GATE_ENABLED", "true")
    assert policy_gate.policy_gate_enabled() is True


def test_policy_engine_url_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_ENGINE_URL", "http://policy-engine.internal:9000/")
    assert policy_gate.policy_engine_url() == "http://policy-engine.internal:9000"
