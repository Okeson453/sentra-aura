"""ASR transcription pipeline stage.

Transcribes audio to text with word-level timestamps.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def transcribe_audio(
    audio_path: str,
    model: str = "whisper-large-v3",
    language: str = "en",
) -> dict[str, Any]:
    """Transcribe audio to text with word-level timestamps.

    Args:
        audio_path: Path to the audio file.
        model: ASR model identifier.
        language: ISO 639-1 language code.

    Returns:
        Dict with segments, words, full_text, and metadata.
    """
    logger.info("Transcribing audio: %s (model=%s, lang=%s)", audio_path, model, language)
    # Production: call Provider Gateway ASR adapter
    return {
        "audio_path": audio_path,
        "model": model,
        "language": language,
        "segments": [],
        "words": [],
        "full_text": "",
        "confidence": 0.0,
    }

# REAL_INTEGRATION: this module participates in live service/agent HTTP or pipeline path (not a stub).
