"""Background worker for async render and transcode tasks.

Processes render jobs from a queue using GPU acceleration when available.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from media_renderer.assembly.timeline_builder import TimelineBuilder
from media_renderer.assembly.compositor import Compositor
from media_renderer.reframing.crop_path_generator import CropPathGenerator
from media_renderer.captioning.caption_renderer import CaptionRenderer
from media_renderer.encoding.ffmpeg_wrapper import FFmpegWrapper
from media_renderer.encoding.codec_profiles import get_profile

logger = logging.getLogger(__name__)


class RenderWorker:
    """Background worker that processes render jobs with GPU acceleration."""

    def __init__(self, poll_interval_seconds: float = 5.0) -> None:
        self.poll_interval = poll_interval_seconds
        self._running = False
        self.gpu_available = self._detect_gpu()
        self.ffmpeg = FFmpegWrapper()
        logger.info("RenderWorker initialized, GPU available=%s", self.gpu_available)

    def _detect_gpu(self) -> bool:
        try:
            result = os.popen("nvidia-smi -L 2>/dev/null").read()
            return len(result.strip()) > 0
        except Exception:
            return False

    async def start(self) -> None:
        self._running = True
        logger.info("RenderWorker started")
        while self._running:
            await self._process_next_job()
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("RenderWorker stopped")

    async def _process_next_job(self) -> None:
        from media_renderer.db.session import get_db
        from media_renderer.db.models import RenderJobORM
        from sqlalchemy.orm import Session
        from datetime import datetime, timezone

        db: Session = next(get_db())
        try:
            job = db.query(RenderJobORM).filter(
                RenderJobORM.status == "queued"
            ).order_by(RenderJobORM.started_at.asc()).first()

            if job:
                logger.info("Found queued job: %s", job.job_id)
                job.status = "processing"
                job.progress_percent = 10
                db.commit()

                try:
                    import json
                    import tempfile
                    from pathlib import Path as _P

                    edl = {}
                    if getattr(job, "edl_json", None):
                        raw = job.edl_json
                        edl = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    elif getattr(job, "metadata_json", None):
                        meta = job.metadata_json if isinstance(job.metadata_json, dict) else {}
                        edl = meta.get("edl") or meta.get("timeline") or {}

                    source_path = (
                        getattr(job, "source_path", None)
                        or (edl.get("source_path") if isinstance(edl, dict) else None)
                        or ""
                    )
                    out_dir = tempfile.mkdtemp(prefix=f"render-{job.job_id}-")
                    output_path = str(_P(out_dir) / f"{job.job_id}.mp4")
                    profile = getattr(job, "profile_name", None) or "youtube_1080p"

                    if source_path and _P(source_path).exists() and edl:
                        result = await self.process_job(
                            job.job_id, edl, output_path, profile_name=profile
                        )
                        if result.get("status") == "completed" and result.get("output_path"):
                            outp = result["output_path"]
                            if _P(outp).exists() and _P(outp).stat().st_size > 0:
                                job.status = "completed"
                                job.progress_percent = 100
                                job.completed_at = datetime.now(timezone.utc)
                                job.output_url = f"file://{outp}"
                                db.commit()
                                logger.info("Job %s completed with real artifact %s", job.job_id, outp)
                            else:
                                job.status = "failed"
                                job.error_message = "encode produced empty or missing file"
                                job.completed_at = datetime.now(timezone.utc)
                                job.output_url = ""
                                db.commit()
                        else:
                            job.status = "failed"
                            job.error_message = result.get("error") or "process_job did not complete"
                            job.completed_at = datetime.now(timezone.utc)
                            job.output_url = ""
                            db.commit()
                    else:
                        job.status = "failed"
                        job.progress_percent = 0
                        job.completed_at = datetime.now(timezone.utc)
                        job.output_url = ""
                        job.error_message = (
                            "encode requires source_path + edl on the job; "
                            "refusing fabricated output_url"
                        )
                        db.commit()
                        logger.warning(
                            "Job %s failed closed: missing source/edl for real encode",
                            job.job_id,
                        )
                except Exception as e:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                    job.output_url = ""
                    db.commit()
                    logger.error("Job %s failed: %s", job.job_id, e)
            else:
                await asyncio.sleep(self.poll_interval)
        finally:
            db.close()

    async def process_job(
        self,
        job_id: str,
        edl: dict[str, Any],
        output_path: str,
        profile_name: str = "youtube_1080p",
        captions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Process a specific render job end-to-end.

        Pipeline: composite → caption → encode with platform profile.
        """
        logger.info("Processing render job %s -> %s", job_id, output_path)

        try:
            compositor = Compositor()
            composite_result = compositor.composite(edl, output_path)
            logger.info("Composition complete: %s", composite_result["status"])

            caption_path = output_path
            if captions:
                caption_renderer = CaptionRenderer()
                caption_path = output_path.replace(".mp4", "_captioned.mp4")
                caption_result = caption_renderer.render(output_path, captions, caption_path)
                logger.info("Caption rendering complete: %s", caption_result["status"])

            profile = get_profile(profile_name)
            encode_path = output_path.replace(".mp4", f"_{profile_name}.mp4")
            encode_result = self.ffmpeg.encode(caption_path, encode_path, profile)
            logger.info("Encoding complete: %s", encode_result["status"])

            return {
                "job_id": job_id,
                "status": "completed",
                "output_path": encode_path,
                "profile": profile_name,
                "gpu_accelerated": self.gpu_available,
            }

        except Exception as exc:
            logger.exception("Render job %s failed", job_id)
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(exc),
            }
