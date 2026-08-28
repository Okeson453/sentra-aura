"""SerpAPI adapter for Google Search, News, and Trends results."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class SerpAPIAdapter(BaseProviderAdapter[dict[str, Any]]):
    """SerpAPI adapter for real-time web search with structured result parsing."""

    MODELS = [
        {"model_id": "google", "name": "Google Search", "capabilities": ["search"]},
        {"model_id": "google_news", "name": "Google News", "capabilities": ["search"]},
        {"model_id": "google_trends", "name": "Google Trends", "capabilities": ["search"]},
    ]

    # Pricing per 1,000 searches
    PRICING = {
        "google": 1.50,
        "google_news": 1.50,
        "google_trends": 1.50,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://serpapi.com/search"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; SerpAPI adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "serpapi"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.SEARCH]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        query = request.get("query", request.get("prompt", ""))
        engine = request.get("engine", "google")
        num_results = request.get("num_results", 10)
        location = request.get("location", "United States")
        language = request.get("language", "en")

        params = {
            "q": query,
            "engine": engine,
            "api_key": self.config.api_key,
            "num": num_results,
            "location": location,
            "hl": language,
            "gl": request.get("country", "us"),
        }

        resp = await self._client.get(self._base_url, params=params)
        resp.raise_for_status()
        data = resp.json()

        organic = []
        for result in data.get("organic_results", []):
            organic.append({
                "title": result.get("title"),
                "link": result.get("link"),
                "snippet": result.get("snippet"),
                "position": result.get("position"),
            })

        return {
            "results": organic,
            "total_results": data.get("search_information", {}).get("total_results"),
            "search_time": data.get("search_information", {}).get("time"),
            "provider": self.provider_id,
            "engine": engine,
            "query": query,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        query = request.get("query", request.get("prompt", ""))
        engine = request.get("engine", "google")
        return {
            "results": [
                {"title": f"Mock result 1 for {query}", "link": "https://example.com/1", "snippet": "..."},
                {"title": f"Mock result 2 for {query}", "link": "https://example.com/2", "snippet": "..."},
            ],
            "total_results": "2",
            "search_time": "0.12",
            "provider": self.provider_id,
            "engine": engine,
            "query": query,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            resp = await self._client.get(
                self._base_url,
                params={"q": "test", "engine": "google", "api_key": self.config.api_key, "num": 1},
            )
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        engine = request.get("engine", "google")
        return round(self.PRICING.get(engine, 1.50) / 1000, 6)
