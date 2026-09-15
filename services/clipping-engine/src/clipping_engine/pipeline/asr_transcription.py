"""ASR transcription pipeline stage.

Transcribes audio to text with word-level timestamps.
Prefers Whisper (local) or provider-gateway when configured; otherwise
produces duration-aligned placeholder segments marked mode=heuristic
(never invents fixed mock strings independent of the media).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from clipping_engine.pipeline.media_probe import probe_duration_seconds, segment_windows

logger = logging.getLogger(__name__)


def _try_whisper(audio_path: str, model: str, language: str) -> dict[str, Any] | None:
    """Attempt local Whisper transcription if the package is installed."""
    try:
        import whisper  # type: ignore
    except ImportError:
        return None
    try:
        wmodel = whisper.load_model(model.replace("whisper-", "") if model.startswith("whisper-") else "base")
        result = wmodel.transcribe(audio_path, language=language or None)
        segments = []
        for seg in result.get("segments") or []:
            words = []
            for w in seg.get("words") or []:
                words.append({
                    "word": w.get("word", "").strip(),
                    "start": float(w.get("start", 0)),
                    "end": float(w.get("end", 0)),
                })
            segments.append({
                "start": float(seg.get("start", 0)),
                "end": float(seg.get("end", 0)),
                "text": (seg.get("text") or "").strip(),
                "words": words,
            })
        return {
            "segments": segments,
            "words": [w for s in segments for w in s["words"]],
            "full_text": (result.get("text") or "").strip(),
            "language": result.get("language") or language,
            "model": model,
            "mode": "whisper",
            "audio_path": audio_path,
        }
    except Exception as exc:
        logger.warning("Whisper transcription failed: %s", exc)
        return None


def _try_provider_gateway(audio_path: str, model: str, language: str) -> dict[str, Any] | None:
    """Optional HTTP call to provider-gateway ASR endpoint when URL is set."""
    base = os.environ.get("PROVIDER_GATEWAY_URL", "").rstrip("/")
    if not base:
        return None
    try:
        import httpx
        with open(audio_path, "rb") as f:
            data = f.read()
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{base}/v1/asr/transcribe",
                files={"file": (Path(audio_path).name, data)},
                data={"model": model, "language": language},
            )
        if resp.status_code >= 400:
            logger.warning("provider-gateway ASR HTTP %s", resp.status_code)
            return None
        body = resp.json()
        body["mode"] = "provider-gateway"
        body["audio_path"] = audio_path
        return body
    except Exception as exc:
        logger.warning("provider-gateway ASR failed: %s", exc)
        return None


def _heuristic_from_duration(audio_path: str, model: str, language: str) -> dict[str, Any]:
    """Duration-aligned empty-ish segments so downstream stages can still run.

    Text is intentionally empty (not fabricated prose). Callers must treat
    mode=heuristic as non-authoritative transcript.
    """
    duration = probe_duration_seconds(audio_path) or 30.0
    windows = segment_windows(duration, window_seconds=5.0)
    segments = []
    for i, (start, end) in enumerate(windows):
        segments.append({
            "start": start,
            "end": end,
            "text": "",
            "words": [],
            "segment_index": i,
        })
    return {
        "segments": segments,
        "words": [],
        "full_text": "",
        "language": language,
        "model": model,
        "mode": "heuristic",
        "audio_path": audio_path,
        "duration_seconds": duration,
        "warning": "No ASR backend available; returned empty duration-aligned segments",
    }


def transcribe_audio(
    audio_path: str,
    model: str = "whisper-large-v3",
    language: str = "en",
) -> dict[str, Any]:
    """Transcribe audio to text with word-level timestamps."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    logger.info("Transcribing audio: %s (model=%s, lang=%s)", audio_path, model, language)

    result = _try_whisper(audio_path, model, language)
    if result is not None:
        return result

    result = _try_provider_gateway(audio_path, model, language)
    if result is not None:
        return result

    return _heuristic_from_duration(audio_path, model, language)
