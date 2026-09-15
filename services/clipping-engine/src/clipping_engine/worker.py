"""Background worker for asynchronous clipping tasks."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import suppress
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import and_, or_, update

from clipping_engine.persistence import ClipJob, SessionLocal
from clipping_engine.pipeline.asr_transcription import transcribe_audio
from clipping_engine.pipeline.audio_extraction import extract_audio
from clipping_engine.pipeline.highlight_scoring import score_highlights
from clipping_engine.pipeline.scene_detection import detect_scenes
from clipping_engine.pipeline.semantic_segmentation import segment_semantically
from clipping_engine.pipeline.shot_detection import detect_shots
from clipping_engine.pipeline.speaker_diarization import diarize_speakers

logger = logging.getLogger(__name__)


class ClippingWorker:
    """Claim and process queued clipping jobs with bounded stale-job retries."""

    def __init__(
        self,
        poll_interval_seconds: float = 5.0,
        *,
        lease_seconds: float = 300.0,
        max_attempts: int = 3,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self._running = False
        logger.info("ClippingWorker initialized")

    async def start(self) -> None:
        self._running = True
        logger.info("ClippingWorker started")
        while self._running:
            processed = await self._process_next_job()
            if not processed:
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("ClippingWorker stopped")

    def _claim_next_job(self) -> dict[str, str] | None:
        """Atomically claim one queued or lease-expired job."""
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=self.lease_seconds)
        eligible = and_(
            ClipJob.attempt_count < self.max_attempts,
            or_(
                ClipJob.status == "queued",
                and_(
                    ClipJob.status == "processing",
                    or_(ClipJob.claimed_at.is_(None), ClipJob.claimed_at < stale_before),
                ),
            ),
        )
        with SessionLocal.begin() as db:
            candidate = db.query(ClipJob.job_id).filter(eligible).order_by(ClipJob.started_at).first()
            if candidate is None:
                return None
            claimed = db.execute(
                update(ClipJob)
                .where(ClipJob.job_id == candidate.job_id, eligible)
                .values(
                    status="processing",
                    progress_percent=10,
                    attempt_count=ClipJob.attempt_count + 1,
                    claimed_at=now,
                    completed_at=None,
                    error_message=None,
                )
                .returning(ClipJob.job_id, ClipJob.video_id)
            ).first()
            if claimed is None:
                return None
            return {"job_id": str(claimed.job_id), "video_id": str(claimed.video_id)}

    async def _process_next_job(self) -> bool:
        job = self._claim_next_job()
        if job is None:
            return False

        job_id = job["job_id"]
        logger.info("Claimed clip job %s", job_id)
        try:
            segments = await self._run_perception_pipeline(job["video_id"])
            scored = score_highlights(segments)
            candidates = scored.get("scored_segments") or scored.get("candidates") or []
            with SessionLocal.begin() as db:
                db.execute(
                    update(ClipJob)
                    .where(ClipJob.job_id == job_id, ClipJob.status == "processing")
                    .values(
                        status="completed",
                        progress_percent=100,
                        candidates=candidates,
                        segment_count=len(candidates),
                        completed_at=datetime.now(timezone.utc),
                        claimed_at=None,
                    )
                )
            logger.info("Clip job %s completed with %d candidates", job_id, len(candidates))
        except Exception as exc:
            with SessionLocal.begin() as db:
                current = db.get(ClipJob, job_id)
                terminal = current is None or current.attempt_count >= self.max_attempts
                db.execute(
                    update(ClipJob)
                    .where(ClipJob.job_id == job_id, ClipJob.status == "processing")
                    .values(
                        status="failed" if terminal else "queued",
                        progress_percent=0,
                        error_message=str(exc),
                        completed_at=datetime.now(timezone.utc) if terminal else None,
                        claimed_at=None,
                    )
                )
            logger.exception("Clip job %s attempt failed", job_id)
        return True

    async def _run_perception_pipeline(self, video_path: str) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        audio_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                audio_path = tmp_audio.name
            extract_audio(video_path, output_path=audio_path)
            asr_result = transcribe_audio(audio_path)
            transcript_segments = asr_result.get("segments", [])
            diarize_speakers(audio_path)
            detect_shots(video_path)
            detect_scenes(video_path)
            semantic_result = segment_semantically(transcript_segments)
            for index, segment in enumerate(semantic_result.get("semantic_segments", [])):
                segments.append(
                    {
                        "segment_id": segment.get("segment_id", f"seg-{index}"),
                        "start_seconds": float(segment.get("start_time", 0)),
                        "end_seconds": float(segment.get("end_time", 5.0)),
                        "text": segment.get("text", ""),
                        "visual_change": 0.5,
                    }
                )
        finally:
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)
        return segments


if __name__ == "__main__":
    worker = ClippingWorker()
    with suppress(KeyboardInterrupt):
        asyncio.run(worker.start())
