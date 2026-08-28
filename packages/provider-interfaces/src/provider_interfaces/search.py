"""Search provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Response from a search provider."""
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    latency_ms: float = 0.0
    provider: str = ""
    trace_id: str = ""
    query_expansion: str = ""


class SearchProvider(ABC):
    """Abstract interface for search providers."""

    @abstractmethod
    async def search(self, query: str, filters: dict[str, Any] | None = None) -> SearchResponse:
        """Execute a search query."""
        ...

    @abstractmethod
    async def web_search(self, query: str, num_results: int = 10) -> SearchResponse:
        """Execute a web search."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
