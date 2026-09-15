"""Speaker diarization pipeline stage.

Identifies speaker turns. Uses pyannote when available; otherwise
duration-based alternating turns marked mode=heuristic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from clipping_engine.pipeline.media_probe import probe_duration_seconds, segment_windows

logger = logging.getLogger(__name__)


def _try_pyannote(audio_path: str, num_speakers: int | None) -> dict[str, Any] | None:
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except ImportError:
        return None
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        diarization = pipeline(audio_path, num_speakers=num_speakers)
        turns = []
        speakers = set()
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.add(speaker)
            turns.append({
                "speaker_id": speaker,
                "start_time": float(turn.start),
                "end_time": float(turn.end),
                "confidence": 0.9,
            })
        return {
            "audio_path": audio_path,
            "num_speakers": len(speakers) or (num_speakers or 1),
            "speaker_turns": turns,
            "mode": "pyannote",
        }
    except Exception as exc:
        logger.warning("pyannote diarization failed: %s", exc)
        return None


def diarize_speakers(
    audio_path: str,
    num_speakers: int | None = None,
) -> dict[str, Any]:
    """Perform speaker diarization on an audio file."""
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    logger.info("Diarizing speakers: %s", audio_path)

    result = _try_pyannote(audio_path, num_speakers)
    if result is not None:
        return result

    duration = probe_duration_seconds(audio_path) or 30.0
    n = num_speakers if num_speakers and num_speakers > 0 else 2
    windows = segment_windows(duration, window_seconds=max(3.0, duration / max(n * 3, 1)))
    turns = []
    for i, (start, end) in enumerate(windows):
        turns.append({
            "speaker_id": f"SPEAKER_{i % n}",
            "start_time": start,
            "end_time": end,
            "confidence": 0.5,
        })
    return {
        "audio_path": audio_path,
        "num_speakers": n,
        "speaker_turns": turns,
        "mode": "heuristic",
        "warning": "No diarization backend; alternating duration-based turns",
    }
