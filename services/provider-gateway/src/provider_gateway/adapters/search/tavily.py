"""Tavily adapter for AI-optimized search with answer synthesis."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class TavilyAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Tavily AI search adapter with answer generation and source filtering."""

    MODELS = [
        {"model_id": "tavily-search", "name": "Tavily Search", "capabilities": ["search"]},
    ]

    # Pricing per 1,000 searches
    PRICING = {
        "tavily-search": 0.80,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.tavily.com"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; Tavily adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "tavily"

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
        max_results = request.get("max_results", 10)
        include_answer = request.get("include_answer", True)
        include_images = request.get("include_images", False)
        search_depth = request.get("search_depth", "basic")  # basic or advanced
        topic = request.get("topic", "general")  # general or news

        resp = await self._client.post("/search", json={
            "query": query,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_images": include_images,
            "search_depth": search_depth,
            "topic": topic,
        })
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title"),
                "url": r.get("url"),
                "content": r.get("content"),
                "score": r.get("score"),
            })

        return {
            "results": results,
            "answer": data.get("answer"),
            "query": query,
            "provider": self.provider_id,
            "total_results": len(results),
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        query = request.get("query", request.get("prompt", ""))
        return {
            "results": [
                {"title": f"Tavily result 1 for {query}", "url": "https://example.com/t1", "content": "...", "score": 0.95},
                {"title": f"Tavily result 2 for {query}", "url": "https://example.com/t2", "content": "...", "score": 0.88},
            ],
            "answer": f"Based on search results, {query} is a topic with significant interest.",
            "query": query,
            "provider": self.provider_id,
            "total_results": 2,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            resp = await self._client.post("/search", json={
                "query": "health check",
                "max_results": 1,
            })
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        depth = request.get("search_depth", "basic")
        multiplier = 2.0 if depth == "advanced" else 1.0
        return round((self.PRICING.get("tavily-search", 0.80) / 1000) * multiplier, 6)
