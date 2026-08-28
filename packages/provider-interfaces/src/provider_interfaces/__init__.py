"""Provider-agnostic AI capability interfaces for SentraAura.

Every AI vendor (LLM, TTS, image, video, etc.) implements these interfaces.
No workflow calls a specific vendor directly.
"""
from __future__ import annotations

from provider_interfaces.llm import LLMProvider, LLMResponse, LLMConfig
from provider_interfaces.tts import TTSProvider, TTSResponse, VoiceProfile
from provider_interfaces.image_generation import ImageGenerationProvider, ImageResponse, ImageConfig
from provider_interfaces.video_generation import VideoGenerationProvider, VideoResponse, VideoConfig
from provider_interfaces.embedding import EmbeddingProvider, EmbeddingResponse
from provider_interfaces.search import SearchProvider, SearchResponse, SearchResult
from provider_interfaces.transcription import TranscriptionProvider, TranscriptResponse, SpeakerSegment
from provider_interfaces.moderation import ModerationProvider, ModerationResult
from provider_interfaces.storage import StorageProvider, StorageResponse
from provider_interfaces.rendering import RenderingProvider, RenderResponse, EDLConfig
from provider_interfaces.publish import PublishProvider, PublishResponse, PublicationMetadata

__all__ = [
    "LLMProvider", "LLMResponse", "LLMConfig",
    "TTSProvider", "TTSResponse", "VoiceProfile",
    "ImageGenerationProvider", "ImageResponse", "ImageConfig",
    "VideoGenerationProvider", "VideoResponse", "VideoConfig",
    "EmbeddingProvider", "EmbeddingResponse",
    "SearchProvider", "SearchResponse", "SearchResult",
    "TranscriptionProvider", "TranscriptResponse", "SpeakerSegment",
    "ModerationProvider", "ModerationResult",
    "StorageProvider", "StorageResponse",
    "RenderingProvider", "RenderResponse", "EDLConfig",
    "PublishProvider", "PublishResponse", "PublicationMetadata",
]
