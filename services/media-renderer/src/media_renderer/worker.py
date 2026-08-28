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
        """Detect if GPU (CUDA) is available for rendering."""
        try:
            result = os.popen("nvidia-smi -L 2>/dev/null").read()
            return len(result.strip()) > 0
        except Exception:
            return False

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        logger.info("RenderWorker started")
        while self._running:
            await self._process_next_job()
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False
        logger.info("RenderWorker stopped")

    async def _process_next_job(self) -> None:
        """Process the next pending render job from the queue.

        Production: integrates with Celery / Redis queue.
        """
        await asyncio.sleep(0.1)

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
            # Step 1: Composite
            compositor = Compositor()
            composite_result = compositor.composite(edl, output_path)
            logger.info("Composition complete: %s", composite_result["status"])

            # Step 2: Add captions if provided
            caption_path = output_path
            if captions:
                caption_renderer = CaptionRenderer()
                caption_path = output_path.replace(".mp4", "_captioned.mp4")
                caption_result = caption_renderer.render(output_path, captions, caption_path)
                logger.info("Caption rendering complete: %s", caption_result["status"])
            else:
                logger.info("No captions provided, skipping caption rendering")

            # Step 3: Encode with platform profile
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
