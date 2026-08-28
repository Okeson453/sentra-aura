"""Mock provider gateway for SentraAura tests."""
from __future__ import annotations

from typing import Any


class MockProviderGateway:
    """Mock AI provider gateway for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self._call_log: list[dict[str, Any]] = []

    def set_response(self, endpoint: str, response: Any) -> None:
        """Set a mock response for an endpoint."""
        self._responses[endpoint] = response

    async def complete(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Mock LLM completion."""
        self._call_log.append({"endpoint": "complete", "prompt": prompt, "kwargs": kwargs})
        return self._responses.get("complete", {
            "text": "Mock completion",
            "provider": "mock",
            "model": "mock-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "estimated_cost_usd": 0.001},
            "latency_ms": 100,
        })

    async def embed(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Mock text embedding."""
        self._call_log.append({"endpoint": "embed", "text": text, "kwargs": kwargs})
        return self._responses.get("embed", {
            "embedding": [0.1] * 1536,
            "provider": "mock",
            "model": "mock-embed",
            "usage": {"prompt_tokens": 5, "estimated_cost_usd": 0.0001},
        })

    async def tts(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Mock text-to-speech."""
        self._call_log.append({"endpoint": "tts", "text": text, "kwargs": kwargs})
        return self._responses.get("tts", {
            "audio_url": "http://mock/tts.mp3",
            "provider": "mock",
            "duration_seconds": 10,
        })

    async def image_generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Mock image generation."""
        self._call_log.append({"endpoint": "image_generate", "prompt": prompt, "kwargs": kwargs})
        return self._responses.get("image_generate", {
            "image_url": "http://mock/image.png",
            "provider": "mock",
            "resolution": "1024x1024",
        })

    def get_call_log(self) -> list[dict[str, Any]]:
        """Get the call log."""
        return self._call_log.copy()

    def reset(self) -> None:
        """Reset the mock state."""
        self._responses.clear()
        self._call_log.clear()
