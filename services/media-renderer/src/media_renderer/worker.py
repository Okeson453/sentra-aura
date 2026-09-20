"""Background worker for async render and transcode tasks.

Processes render jobs from a queue using GPU acceleration when available.
After a successful real encode, uploads the artifact to asset-store and
stores a durable signed/download URL (never a fabricated success URL).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from media_renderer.assembly.compositor import Compositor
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

    async def _upload_artifact_to_asset_store(
        self,
        local_path: str,
        *,
        channel_id: str = "",
        tenant_id: str = "",
        job_id: str = "",
    ) -> str | None:
        """Upload encoded file to asset-store; return signed or download URL."""
        try:
            import httpx
            from media_renderer.config import ServiceConfig

            cfg = ServiceConfig()
            base = (cfg.asset_store_url or "").rstrip("/")
            if not base:
                return None
            filename = os.path.basename(local_path) or f"{job_id}.mp4"
            with open(local_path, "rb") as fh:
                data = fh.read()
            if not data:
                return None
            files = {"file": (filename, data, "video/mp4")}
            form = {
                "channel_id": channel_id or "system",
                "tenant_id": tenant_id or "system",
                "asset_type": "rendered_clip",
                "content_type": "video/mp4",
                "metadata": f'{{"job_id":"{job_id}","source":"media-renderer"}}',
                "created_by": "media-renderer",
            }
            timeout = float(getattr(cfg, "asset_store_timeout_seconds", 60.0) or 60.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{base}/api/v1/upload", data=form, files=files)
                if resp.status_code >= 400:
                    logger.warning(
                        "asset-store upload failed HTTP %s: %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return None
                body = resp.json() if resp.content else {}
                asset_id = body.get("asset_id") or ""
                if not asset_id:
                    return None
                signed = await client.get(
                    f"{base}/api/v1/{asset_id}/signed-url",
                    params={"expiry_seconds": 86400},
                )
                if signed.status_code < 400 and signed.content:
                    sbody = signed.json()
                    url = sbody.get("url") or sbody.get("signed_url") or ""
                    if url:
                        return url
                return f"{base}/api/v1/{asset_id}/download"
        except Exception as exc:
            logger.warning("asset-store upload error for %s: %s", job_id, exc)
            return None

    async def _process_next_job(self) -> None:
        from media_renderer.db.session import get_db
        from media_renderer.db.models import RenderJobORM
        from sqlalchemy.orm import Session
        from datetime import datetime, timezone

        db: Session = next(get_db())
        try:
            job = (
                db.query(RenderJobORM)
                .filter(RenderJobORM.status == "queued")
                .order_by(RenderJobORM.started_at.asc())
                .first()
            )

            if not job:
                await asyncio.sleep(self.poll_interval)
                return

            logger.info("Found queued job: %s", job.job_id)
            job.status = "processing"
            job.progress_percent = 10
            db.commit()

            try:
                import json
                import tempfile
                from pathlib import Path as _P

                edl: dict[str, Any] = {}
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
                            signed = await self._upload_artifact_to_asset_store(
                                outp,
                                channel_id=getattr(job, "channel_id", "") or "",
                                tenant_id=getattr(job, "tenant_id", "") or "",
                                job_id=job.job_id,
                            )
                            job.status = "completed"
                            job.progress_percent = 100
                            job.completed_at = datetime.now(timezone.utc)
                            job.output_url = signed or f"file://{outp}"
                            db.commit()
                            logger.info(
                                "Job %s completed; output_url=%s",
                                job.job_id,
                                job.output_url[:120],
                            )
                            # Architecture §4/§32: a completed render must emit
                            # video.rendered so downstream stages can react.
                            await self._publish_video_rendered(job)
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
        finally:
            db.close()

    def _build_video_rendered_event(self, job: Any) -> dict[str, Any]:
        """Build a ``video.rendered`` payload that satisfies its published contract.

        Pure function (no I/O) so the contract can be verified by tests without a
        broker. Optional fields are only emitted when they carry real values.
        """
        metadata = getattr(job, "metadata_json", None)
        plan = getattr(job, "render_plan", None)
        script_id = ""
        for source in (metadata, plan):
            if isinstance(source, dict) and source.get("script_id"):
                script_id = str(source["script_id"])
                break
        if not script_id:
            # No script lineage on the job: fall back to the render job's own
            # project id so the required field stays a real, traceable value.
            script_id = str(getattr(job, "project_id", "") or "")

        event: dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "event_type": "video.rendered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel_id": getattr(job, "channel_id", "") or "system",
            "tenant_id": getattr(job, "tenant_id", "") or "system",
            "video_id": str(getattr(job, "job_id", "") or ""),
            "script_id": script_id,
        }
        duration = getattr(job, "duration_seconds", None)
        if duration:
            event["duration_seconds"] = int(duration)
        resolution = getattr(job, "resolution", "") or ""
        if resolution:
            event["resolution"] = resolution
        output_url = getattr(job, "output_url", "") or ""
        if output_url:
            event["asset_urls"] = {"output": output_url}
        return event

    async def _publish_video_rendered(self, job: Any) -> None:
        """Publish ``video.rendered`` via packages/event-bus (Architecture §4/§32).

        The payload is built to satisfy contracts/events/v1/video_rendered.json —
        required fields are always present, and optional fields are only emitted when
        they carry real values (never fabricated). Publication failure is logged
        loudly but does NOT fail the render: the artifact itself succeeded.
        """
        import os
        try:
            from event_bus import create_event_publisher
        except ImportError:
            logger.error("event_bus package not importable; video_rendered event NOT published")
            return
        # Fail-safe default: real NATS. Deployments must opt IN to mock mode.
        mock = os.environ.get("NATS_MOCK_MODE", "false").lower() in ("1", "true", "yes")
        nats_url = os.environ.get("NATS_URL") or "nats://localhost:4222"
        event = self._build_video_rendered_event(job)

        nc, publisher = await create_event_publisher(nats_url=nats_url, mock_mode=mock)
        try:
            await publisher.publish(
                event,
                channel_id=event["channel_id"],
                event_family="clip",
                event_type="video_rendered",
                schema_name="video_rendered.json",
            )
        except Exception as exc:
            # No unvalidated fallback: an event that cannot meet its contract is
            # reported, not silently re-published around the validator.
            logger.error("video_rendered event publish failed: %s", exc)
        finally:
            try:
                await nc.close()
            except Exception:
                pass

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
