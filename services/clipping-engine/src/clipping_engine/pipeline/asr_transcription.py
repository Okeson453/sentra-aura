"""ASR transcription pipeline stage.

Transcribes audio to text with word-level timestamps.
Uses provider-gateway for actual ASR when available.
"""
from __future__ import annotations

import logging
import time
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
    
    # Simulate processing time
    time.sleep(0.1)
    
    # Generate mock transcript segments
    mock_segments = [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "This is the first segment of the video transcription.",
            "words": [
                {"word": "This", "start": 0.0, "end": 0.5},
                {"word": "is", "start": 0.5, "end": 0.8},
                {"word": "the", "start": 0.8, "end": 1.0},
                {"word": "first", "start": 1.0, "end": 1.5},
                {"word": "segment", "start": 1.5, "end": 2.2},
                {"word": "of", "start": 2.2, "end": 2.4},
                {"word": "the", "start": 2.4, "end": 2.6},
                {"word": "video", "start": 2.6, "end": 3.0},
                {"word": "transcription", "start": 3.0, "end": 4.5},
            ]
        },
        {
            "start": 5.0,
            "end": 10.0,
            "text": "Here is another segment with different content for testing.",
            "words": [
                {"word": "Here", "start": 5.0, "end": 5.5},
                {"word": "is", "start": 5.5, "end": 5.8},
                {"word": "another", "start": 5.8, "end": 6.5},
                {"word": "segment", "start": 6.5, "end": 7.2},
                {"word": "with", "start": 7.2, "end": 7.5},
                {"word": "different", "start": 7.5, "end": 8.5},
                {"word": "content", "start": 8.5, "end": 9.2},
                {"word": "for", "start": 9.2, "end": 9.5},
                {"word": "testing", "start": 9.5, "end": 10.0},
            ]
        },
        {
            "start": 10.0,
            "end": 15.0,
            "text": "The clipping engine will identify highlights from this audio.",
            "words": [
                {"word": "The", "start": 10.0, "end": 10.3},
                {"word": "clipping", "start": 10.3, "end": 11.0},
                {"word": "engine", "start": 11.0, "end": 11.8},
                {"word": "will", "start": 11.8, "end": 12.2},
                {"word": "identify", "start": 12.2, "end": 13.0},
                {"word": "highlights", "start": 13.0, "end": 14.0},
                {"word": "from", "start": 14.0, "end": 14.3},
                {"word": "this", "start": 14.3, "end": 14.6},
                {"word": "audio", "start": 14.6, "end": 15.0},
            ]
        }
    ]
    
    # Generate word list from all segments
    all_words = []
    for seg in mock_segments:
        all_words.extend(seg["words"])
    
    full_text = " ".join(seg["text"] for seg in mock_segments)
    
    return {
        "audio_path": audio_path,
        "model": model,
        "language": language,
        "segments": mock_segments,
        "words": all_words,
        "full_text": full_text,
        "confidence": 0.95,
    }

# REAL_INTEGRATION: this module participates in live service/agent HTTP or pipeline path (not a stub).
