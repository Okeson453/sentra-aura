"""Tests for provider interfaces."""
from __future__ import annotations

import pytest
from provider_interfaces.llm import LLMConfig, LLMResponse
from provider_interfaces.tts import VoiceProfile, TTSResponse
from provider_interfaces.image_generation import ImageConfig, ImageResponse
from provider_interfaces.video_generation import VideoConfig, VideoResponse
from provider_interfaces.embedding import EmbeddingResponse
from provider_interfaces.search import SearchResult, SearchResponse
from provider_interfaces.transcription import SpeakerSegment, TranscriptResponse
from provider_interfaces.moderation import ModerationResult
from provider_interfaces.storage import StorageResponse
from provider_interfaces.rendering import EDLConfig, RenderResponse
from provider_interfaces.publish import PublicationMetadata, PublishResponse


def test_llm_config_defaults():
    cfg = LLMConfig()
    assert cfg.model == "gpt-4"
    assert cfg.temperature == 0.7


def test_llm_response_defaults():
    resp = LLMResponse(content="hello", model="gpt-4")
    assert resp.content == "hello"
    assert resp.total_tokens == 0


def test_voice_profile():
    vp = VoiceProfile(voice_id="v1", name="Test")
    assert vp.speed == 1.0


def test_image_config():
    cfg = ImageConfig()
    assert cfg.aspect_ratio == "16:9"


def test_video_config():
    cfg = VideoConfig()
    assert cfg.resolution == "1080p"


def test_embedding_response():
    resp = EmbeddingResponse(vector=[0.1, 0.2], dimension=2)
    assert len(resp.vector) == 2


def test_search_result():
    sr = SearchResult(title="T", url="http://example.com")
    assert sr.title == "T"


def test_speaker_segment():
    seg = SpeakerSegment(speaker_id="S1", start_ms=0, end_ms=1000)
    assert seg.speaker_id == "S1"


def test_moderation_result():
    mr = ModerationResult()
    assert mr.flagged is False


def test_storage_response():
    sr = StorageResponse(url="s3://bucket/key")
    assert sr.path == ""


def test_edl_config():
    edl = EDLConfig()
    assert edl.output_resolution == "1920x1080"


def test_publication_metadata():
    pm = PublicationMetadata(title="Test")
    assert pm.privacy == "public"
