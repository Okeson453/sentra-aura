"""Background worker for async clip detection tasks.

Processes detection jobs from a queue with GPU-aware scheduling.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from clipping_engine.pipeline.audio_extraction import extract_audio
from clipping_engine.pipeline.asr_transcription import transcribe_audio
from clipping_engine.pipeline.shot_detection import detect_shots
from clipping_engine.pipeline.scene_detection import detect_scenes
from clipping_engine.pipeline.semantic_segmentation import segment_semantically
from clipping_engine.pipeline.highlight_scoring import score_highlights

logger = logging.getLogger(__name__)


class ClipDetectionWorker:
    """Background worker that processes clip detection jobs with GPU awareness."""

    def __init__(self, poll_interval_seconds: float = 5.0) -> None:
        self.poll_interval = poll_interval_seconds
        self._running = False
        self.gpu_available = self._detect_gpu()
        logger.info("ClipDetectionWorker initialized, GPU available=%s", self.gpu_available)

    def _detect_gpu(self) -> bool:
        """Detect if GPU (CUDA) is available for inference."""
        try:
            result = os.popen("nvidia-smi -L 2>/dev/null").read()
            return len(result.strip()) > 0
        except Exception:
            return False

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        logger.info("ClipDetectionWorker started")
        while self._running:
            await self._process_next_job()
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False
        logger.info("ClipDetectionWorker stopped")

    async def _process_next_job(self) -> None:
        """Process the next pending job from the queue.

        Production: integrates with Celery / Redis queue.
        """
        # Placeholder for queue integration
        await asyncio.sleep(0.1)

    async def process_job(self, job_id: str, video_path: str) -> dict[str, Any]:
        """Process a specific detection job end-to-end.

        Pipeline: audio extraction → ASR → shot detection → scene detection
        → semantic segmentation → highlight scoring.
        """
        logger.info("Processing clip detection job %s for %s", job_id, video_path)

        try:
            # Step 1: Extract audio
            audio_result = extract_audio(video_path)
            logger.info("Audio extracted: %s", audio_result["output_path"])

            # Step 2: Transcribe
            transcript = transcribe_audio(audio_result["output_path"])
            logger.info("Transcription complete: %d segments", len(transcript.get("segments", [])))

            # Step 3: Detect shots
            shots = detect_shots(video_path)
            logger.info("Shot detection: %d shots", len(shots.get("shot_boundaries", [])))

            # Step 4: Detect scenes
            scenes = detect_scenes(video_path, shot_boundaries=shots.get("shot_boundaries"))
            logger.info("Scene detection: %d scenes", len(scenes.get("scenes", [])))

            # Step 5: Semantic segmentation
            semantic = segment_semantically(transcript.get("segments", []))
            logger.info("Semantic segmentation: %d segments", len(semantic.get("semantic_segments", [])))

            # Step 6: Highlight scoring
            highlights = score_highlights(semantic.get("semantic_segments", []))
            logger.info("Highlight scoring complete")

            return {
                "job_id": job_id,
                "status": "completed",
                "video_path": video_path,
                "audio_path": audio_result["output_path"],
                "transcript_segments": len(transcript.get("segments", [])),
                "shot_boundaries": len(shots.get("shot_boundaries", [])),
                "scenes": len(scenes.get("scenes", [])),
                "semantic_segments": len(semantic.get("semantic_segments", [])),
                "gpu_accelerated": self.gpu_available,
            }

        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            return {
                "job_id": job_id,
                "status": "failed",
                "error": str(exc),
            }
