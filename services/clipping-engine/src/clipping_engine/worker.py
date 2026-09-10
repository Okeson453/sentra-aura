"""Background worker for async clipping tasks.

Processes clip detection jobs from the database queue.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from clipping_engine.config import ServiceConfig
from clipping_engine.db.session import get_db
from clipping_engine.pipeline.audio_extraction import extract_audio
from clipping_engine.pipeline.asr_transcription import transcribe_audio
from clipping_engine.pipeline.speaker_diarization import diarize_speakers
from clipping_engine.pipeline.shot_detection import detect_shots
from clipping_engine.pipeline.scene_detection import detect_scenes
from clipping_engine.pipeline.semantic_segmentation import segment_semantically
from clipping_engine.pipeline.highlight_scoring import score_highlights

logger = logging.getLogger(__name__)

config = ServiceConfig()


class ClippingWorker:
    """Background worker that processes clipping jobs."""

    def __init__(self, poll_interval_seconds: float = 5.0) -> None:
        self.poll_interval = poll_interval_seconds
        self._running = False
        logger.info("ClippingWorker initialized")

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        logger.info("ClippingWorker started")
        while self._running:
            await self._process_next_job()
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False
        logger.info("ClippingWorker stopped")

    async def _process_next_job(self) -> None:
        """Process the next pending clip job from the database queue."""
        from sqlalchemy import text
        from sqlalchemy.orm import Session
        
        db: Session = next(get_db())
        try:
            result = db.execute(text("""
                SELECT job_id, video_id, channel_id, tenant_id 
                FROM clip_jobs 
                WHERE status = 'queued' 
                ORDER BY started_at ASC 
                LIMIT 1
            """))
            job = result.fetchone()
            
            if job:
                job_id = job[0]
                video_id = job[1]
                
                logger.info("Found queued clip job: %s (video: %s)", job_id, video_id)
                
                db.execute(text("""
                    UPDATE clip_jobs 
                    SET status = 'processing', progress_percent = 10 
                    WHERE job_id = :job_id
                """), {"job_id": job_id})
                db.commit()
                
                try:
                    segments = await self._run_perception_pipeline(video_id)
                    scored = score_highlights(segments)
                    candidates = scored.get("scored_segments") or scored.get("candidates") or []
                    
                    db.execute(text("""
                        UPDATE clip_jobs 
                        SET status = 'completed', 
                            progress_percent = 100, 
                            candidates = :candidates, 
                            segment_count = :count, 
                            completed_at = :now
                        WHERE job_id = :job_id
                    """), {
                        "job_id": job_id,
                        "candidates": str(candidates),
                        "count": len(candidates),
                        "now": datetime.utcnow()
                    })
                    db.commit()
                    logger.info("Clip job %s completed with %d candidates", job_id, len(candidates))
                    
                except Exception as e:
                    db.execute(text("""
                        UPDATE clip_jobs 
                        SET status = 'failed', 
                            error_message = :error, 
                            completed_at = :now
                        WHERE job_id = :job_id
                    """), {
                        "job_id": job_id,
                        "error": str(e),
                        "now": datetime.utcnow()
                    })
                    db.commit()
                    logger.error("Clip job %s failed: %s", job_id, e)
            else:
                await asyncio.sleep(self.poll_interval)
        except Exception as e:
            logger.error("Error processing clip jobs: %s", e)
        finally:
            db.close()

    async def _run_perception_pipeline(self, video_path: str) -> list[dict[str, Any]]:
        """Run the full perception pipeline to generate segments from video."""
        import tempfile
        import os
        
        segments = []
        audio_path = None
        
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
            semantic_segments = semantic_result.get("semantic_segments", [])
            
            for i, seg in enumerate(semantic_segments):
                segments.append({
                    "segment_id": seg.get("segment_id", f"seg-{i}"),
                    "start_seconds": float(seg.get("start_time", 0)),
                    "end_seconds": float(seg.get("end_time", 5.0)),
                    "text": seg.get("text", ""),
                    "visual_change": 0.5,
                })
            
        except Exception as e:
            logger.warning("Pipeline failed: %s", e)
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass
        
        return segments


if __name__ == "__main__":
    import sys
    worker = ClippingWorker()
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        sys.exit(0)
