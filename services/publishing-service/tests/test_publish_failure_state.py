"""Regression tests for truthful publishing terminal states."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from publishing_service import main


@pytest.mark.asyncio
async def test_platform_failure_does_not_mark_job_or_publication_success(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(main.config.database_url)
    session = sessionmaker(bind=engine)()
    suffix = uuid.uuid4().hex
    publication = main.Publication(
        publication_id=f"pub-{suffix[:12]}",
        channel_id="channel",
        title="title",
        description="description",
        status="publishing",
        asset_id="video.mp4",
        platforms=["youtube"],
        tags=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    job = main.PublishJob(
        job_id=f"publish-{suffix[:12]}",
        publication_id=publication.publication_id,
        status="publishing",
        platform_results=[],
        started_at=datetime.now(timezone.utc),
    )
    session.add_all([publication, job])
    session.commit()

    async def failed_publish(platform_id: str, pub: main.Publication) -> dict[str, object]:
        raise RuntimeError("YouTube rejected upload")

    monkeypatch.setattr(main, "_publish_to_platform", failed_publish)
    # The job opens its own session and re-reads the publication: the request
    # scoped session handed to the endpoint is closed as soon as the request
    # returns, so passing it (and a detached instance) here could never work in
    # production. Give the job its own session from the same engine (it closes
    # that one), and assert through this test's still-open session.
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    try:
        await main._process_publish_job(
            job.job_id,
            publication.publication_id,
        )
        session.refresh(job)
        session.refresh(publication)
        assert job.status == "failed"
        assert publication.status == "failed"
        assert job.status != "completed"
        assert publication.status != "published"
        assert job.platform_results == [
            {"platform": "youtube", "status": "failed", "error": "YouTube rejected upload"}
        ]
        assert job.error_message == "youtube: YouTube rejected upload"
    finally:
        session.delete(job)
        session.delete(publication)
        session.commit()
        session.close()
        engine.dispose()


def test_youtube_thumbnail_failure_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    from publishing_service.platforms import youtube

    video_path = tmp_path / "video.mp4"
    thumbnail_path = tmp_path / "thumbnail.jpg"
    video_path.write_bytes(b"video")
    thumbnail_path.write_bytes(b"thumbnail")

    class Request:
        def __init__(self, result=None, error=None):
            self.result = result
            self.error = error

        def execute(self):
            if self.error:
                raise self.error
            return self.result

    service = SimpleNamespace(
        videos=lambda: SimpleNamespace(insert=lambda **kwargs: Request({"id": "video-1"})),
        thumbnails=lambda: SimpleNamespace(
            set=lambda **kwargs: Request(error=youtube.HttpError(SimpleNamespace(status=500, reason="error"), b"{}"))
        ),
    )
    adapter = youtube.YouTubeAdapter(api_key="key")
    monkeypatch.setattr(adapter, "_get_service", lambda: service)
    monkeypatch.setattr(youtube, "MediaFileUpload", lambda *args, **kwargs: object())

    with pytest.raises(RuntimeError, match="thumbnail upload failed"):
        adapter.upload(
            str(video_path),
            "title",
            "description",
            thumbnail_path=str(thumbnail_path),
        )
