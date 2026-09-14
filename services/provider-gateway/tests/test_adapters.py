"""Tests for individual provider adapters."""

from __future__ import annotations

import pytest

from provider_gateway.config import ProviderConfig
from provider_gateway.adapters.llm.openai import OpenAIAdapter
from provider_gateway.adapters.llm.anthropic import AnthropicAdapter
from provider_gateway.adapters.llm.google import GoogleAdapter
from provider_gateway.adapters.llm.cohere import CohereAdapter
from provider_gateway.adapters.llm.mistral import MistralAdapter
from provider_gateway.adapters.tts.elevenlabs import ElevenLabsAdapter
from provider_gateway.adapters.tts.azure import AzureTTSAdapter
from provider_gateway.adapters.tts.aws import AWSTTSAdapter
from provider_gateway.adapters.image.dalle import DALLEAdapter
from provider_gateway.adapters.image.midjourney import MidjourneyAdapter
from provider_gateway.adapters.image.stablediffusion import StableDiffusionAdapter
from provider_gateway.adapters.video.runway import RunwayAdapter
from provider_gateway.adapters.video.pika import PikaAdapter
from provider_gateway.adapters.search.serpapi import SerpAPIAdapter
from provider_gateway.adapters.search.tavily import TavilyAdapter
from provider_gateway.adapters.transcription.whisper import WhisperAdapter
from provider_gateway.adapters.transcription.assemblyai import AssemblyAIAdapter
from provider_gateway.adapters.base import ProviderCapability


@pytest.fixture
def cfg() -> ProviderConfig:
    """Adapter config for unit tests.

    ``mock_mode=True`` is explicit and load-bearing: the adapters now make a
    real network call whenever a credential is present (``api_key`` here is the
    placeholder ``test-key``), so without this flag every "mock" test in this
    module would issue live requests to the upstream provider. Mock mode is
    requested deliberately rather than inherited from a broken client object.
    """
    return ProviderConfig(provider_id="test", api_key="test-key", enabled=True, mock_mode=True)


class TestOpenAIAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = OpenAIAdapter(cfg)
        assert ProviderCapability.LLM_COMPLETE in adapter.capabilities
        assert ProviderCapability.EMBED in adapter.capabilities

    def test_estimate_cost_completion(self, cfg: ProviderConfig) -> None:
        adapter = OpenAIAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "hello world", "max_tokens": 100, "model": "gpt-4o"})
        assert cost > 0

    def test_estimate_cost_embedding(self, cfg: ProviderConfig) -> None:
        adapter = OpenAIAdapter(cfg)
        cost = adapter.estimate_cost({"text": "hello world", "model": "text-embedding-3-small"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = OpenAIAdapter(cfg)
        result = await adapter.execute({"prompt": "test", "model": "gpt-4o"})
        assert "text" in result
        assert result["model"] == "gpt-4o"


class TestAnthropicAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = AnthropicAdapter(cfg)
        assert ProviderCapability.LLM_COMPLETE in adapter.capabilities
        assert ProviderCapability.EMBED not in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = AnthropicAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "hello", "max_tokens": 100, "model": "claude-3-5-sonnet-20241022"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = AnthropicAdapter(cfg)
        result = await adapter.execute({"prompt": "test", "model": "claude-3-5-sonnet-20241022"})
        assert "text" in result


class TestGoogleAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = GoogleAdapter(cfg)
        assert ProviderCapability.LLM_COMPLETE in adapter.capabilities
        assert ProviderCapability.EMBED in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = GoogleAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "hello", "max_tokens": 100})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = GoogleAdapter(cfg)
        result = await adapter.execute({"prompt": "test"})
        assert "text" in result


class TestCohereAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = CohereAdapter(cfg)
        assert ProviderCapability.LLM_COMPLETE in adapter.capabilities
        assert ProviderCapability.EMBED in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = CohereAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "hello", "max_tokens": 100})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = CohereAdapter(cfg)
        result = await adapter.execute({"prompt": "test"})
        assert "text" in result


class TestMistralAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = MistralAdapter(cfg)
        assert ProviderCapability.LLM_COMPLETE in adapter.capabilities
        assert ProviderCapability.EMBED in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = MistralAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "hello", "max_tokens": 100})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = MistralAdapter(cfg)
        result = await adapter.execute({"prompt": "test"})
        assert "text" in result


class TestElevenLabsAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = ElevenLabsAdapter(cfg)
        assert ProviderCapability.TTS in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = ElevenLabsAdapter(cfg)
        cost = adapter.estimate_cost({"text": "Hello world this is a test"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = ElevenLabsAdapter(cfg)
        result = await adapter.execute({"text": "Hello world"})
        assert "audio_url" in result


class TestAzureTTSAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = AzureTTSAdapter(cfg)
        assert ProviderCapability.TTS in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = AzureTTSAdapter(cfg)
        cost = adapter.estimate_cost({"text": "Hello world"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = AzureTTSAdapter(cfg)
        result = await adapter.execute({"text": "Hello world"})
        assert "audio_url" in result


class TestAWSTTSAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = AWSTTSAdapter(cfg)
        assert ProviderCapability.TTS in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = AWSTTSAdapter(cfg)
        cost = adapter.estimate_cost({"text": "Hello world", "engine": "neural"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = AWSTTSAdapter(cfg)
        result = await adapter.execute({"text": "Hello world"})
        assert "audio_url" in result


class TestDALLEAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = DALLEAdapter(cfg)
        assert ProviderCapability.IMAGE_GENERATE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = DALLEAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "a cat", "size": "1024x1024", "model": "dall-e-3"})
        assert cost == 0.04

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = DALLEAdapter(cfg)
        result = await adapter.execute({"prompt": "a cat"})
        assert "image_url" in result


class TestMidjourneyAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = MidjourneyAdapter(cfg)
        assert ProviderCapability.IMAGE_GENERATE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = MidjourneyAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "a cat"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = MidjourneyAdapter(cfg)
        result = await adapter.execute({"prompt": "a cat"})
        assert "image_url" in result


class TestStableDiffusionAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = StableDiffusionAdapter(cfg)
        assert ProviderCapability.IMAGE_GENERATE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = StableDiffusionAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "a cat"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = StableDiffusionAdapter(cfg)
        result = await adapter.execute({"prompt": "a cat"})
        assert "image_url" in result


class TestRunwayAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = RunwayAdapter(cfg)
        assert ProviderCapability.VIDEO_GENERATE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = RunwayAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "a cat", "duration_seconds": 5})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = RunwayAdapter(cfg)
        result = await adapter.execute({"prompt": "a cat"})
        assert "video_url" in result


class TestPikaAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = PikaAdapter(cfg)
        assert ProviderCapability.VIDEO_GENERATE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = PikaAdapter(cfg)
        cost = adapter.estimate_cost({"prompt": "a cat", "duration_seconds": 5})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = PikaAdapter(cfg)
        result = await adapter.execute({"prompt": "a cat"})
        assert "video_url" in result


class TestSerpAPIAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = SerpAPIAdapter(cfg)
        assert ProviderCapability.SEARCH in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = SerpAPIAdapter(cfg)
        cost = adapter.estimate_cost({"query": "test"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = SerpAPIAdapter(cfg)
        result = await adapter.execute({"query": "test"})
        assert "results" in result


class TestTavilyAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = TavilyAdapter(cfg)
        assert ProviderCapability.SEARCH in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = TavilyAdapter(cfg)
        cost = adapter.estimate_cost({"query": "test"})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = TavilyAdapter(cfg)
        result = await adapter.execute({"query": "test"})
        assert "results" in result
        assert "answer" in result


class TestWhisperAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = WhisperAdapter(cfg)
        assert ProviderCapability.TRANSCRIBE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = WhisperAdapter(cfg)
        cost = adapter.estimate_cost({"audio_url": "https://example.com/audio.mp3", "duration_seconds": 120})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = WhisperAdapter(cfg)
        result = await adapter.execute({"audio_url": "https://example.com/audio.mp3"})
        assert "text" in result


class TestAssemblyAIAdapter:
    def test_capabilities(self, cfg: ProviderConfig) -> None:
        adapter = AssemblyAIAdapter(cfg)
        assert ProviderCapability.TRANSCRIBE in adapter.capabilities

    def test_estimate_cost(self, cfg: ProviderConfig) -> None:
        adapter = AssemblyAIAdapter(cfg)
        cost = adapter.estimate_cost({"audio_url": "https://example.com/audio.mp3", "duration_seconds": 3600})
        assert cost > 0

    @pytest.mark.asyncio
    async def test_mock_execute(self, cfg: ProviderConfig) -> None:
        adapter = AssemblyAIAdapter(cfg)
        result = await adapter.execute({"audio_url": "https://example.com/audio.mp3"})
        assert "text" in result
        assert "utterances" in result


class TestMockModeIsKeyedOnCredential:
    """Regression guard for the P0 where mock mode was keyed on whether the
    ``httpx`` *library* was importable (it always is - it is a hard dependency)
    rather than on the presence of a credential.

    With no credential the adapters therefore built a live client with
    ``api_key=None`` and issued real, billable requests to the upstream provider,
    leaking the key in query strings (SerpAPI/AssemblyAI). Every test below
    fails against that implementation and passes only when a credential-less
    adapter is guaranteed not to reach the network.
    """

    def test_no_credential_selects_mock_mode(self) -> None:
        adapter = MidjourneyAdapter(ProviderConfig(provider_id="test", api_key=None, enabled=True))
        assert adapter._is_mock() is True

    def test_credential_selects_live_mode_by_default(self) -> None:
        adapter = MidjourneyAdapter(ProviderConfig(provider_id="test", api_key="real-key", enabled=True))
        assert adapter._is_mock() is False

    def test_explicit_mock_mode_overrides_present_credential(self) -> None:
        adapter = MidjourneyAdapter(
            ProviderConfig(provider_id="test", api_key="real-key", enabled=True, mock_mode=True)
        )
        assert adapter._is_mock() is True

    @pytest.mark.asyncio
    async def test_credentialless_adapter_never_touches_the_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The core assertion: without a credential the adapter must not call out."""
        import httpx

        def _explode(*args: object, **kwargs: object) -> object:
            raise AssertionError("adapter attempted a live network call with no credential")

        monkeypatch.setattr(httpx.AsyncClient, "post", _explode)
        monkeypatch.setattr(httpx.AsyncClient, "get", _explode)

        adapter = MidjourneyAdapter(ProviderConfig(provider_id="test", api_key=None, enabled=True))
        result = await adapter.execute({"prompt": "test", "model": "midjourney-v6"})
        assert result["image_url"]
        assert result["provider"] == "midjourney"

    @pytest.mark.asyncio
    async def test_serpapi_credentialless_does_not_call_or_leak(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SerpAPI put the key in the query string; with no key it must not call."""
        import httpx

        def _explode(*args: object, **kwargs: object) -> object:
            raise AssertionError("serpapi adapter attempted a live search with no credential")

        monkeypatch.setattr(httpx.AsyncClient, "get", _explode)

        adapter = SerpAPIAdapter(ProviderConfig(provider_id="test", api_key=None, enabled=True))
        result = await adapter.execute({"query": "test"})
        assert result["results"]
        assert result["provider"] == "serpapi"
