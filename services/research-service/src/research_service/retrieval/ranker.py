"""Source credibility ranker with domain authority, recency, and bias scoring.

Ranks research sources by a composite credibility score that combines
domain reputation, content freshness, cross-reference coverage, and
known bias indicators.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from research_service.config import ResearchConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RankedSource:
    """A source with its computed credibility ranking."""

    source_id: str
    url: str | None
    title: str
    content: str | None
    credibility_score: float
    domain_authority: float
    recency_score: float
    bias_penalty: float
    cross_reference_count: int
    source_type: str
    rank: int


class SourceRanker:
    """Ranks sources by composite credibility."""

    # Known high-credibility domains and their base authority scores
    DOMAIN_AUTHORITY_MAP: dict[str, float] = {
        # Academic
        "arxiv.org": 0.95,
        "pubmed.ncbi.nlm.nih.gov": 0.95,
        "nature.com": 0.95,
        "science.org": 0.95,
        "ieee.org": 0.92,
        "acm.org": 0.92,
        # Government
        "gov": 0.90,
        "europa.eu": 0.90,
        "un.org": 0.88,
        # Established news
        "reuters.com": 0.85,
        "apnews.com": 0.85,
        "bbc.com": 0.82,
        "bbc.co.uk": 0.82,
        "nytimes.com": 0.80,
        "washingtonpost.com": 0.78,
        "theguardian.com": 0.78,
        "economist.com": 0.85,
        "ft.com": 0.82,
        "bloomberg.com": 0.80,
        # Industry / tech
        "techcrunch.com": 0.65,
        "theverge.com": 0.65,
        "wired.com": 0.70,
        # Reference
        "wikipedia.org": 0.60,
        "britannica.com": 0.75,
    }

    # Known low-credibility / high-bias indicators
    BIAS_DOMAIN_PATTERNS: list[str] = [
        "clickbait",
        "conspiracy",
        "fake",
        "satire",
        "tabloid",
    ]

    def __init__(self, config: ResearchConfig) -> None:
        self.config = config

    def rank(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank a list of raw sources by composite credibility."""
        # Deduplicate by URL, keeping first occurrence
        seen_urls: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for src in sources:
            url = src.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            deduped.append(src)

        scored: list[tuple[float, dict[str, Any]]] = []
        for src in deduped:
            score = self._compute_score(src)
            src["credibility_score"] = round(score, 3)
            scored.append((score, src))

        scored.sort(key=lambda x: x[0], reverse=True)
        for i, (_, src) in enumerate(scored, start=1):
            src["rank"] = i

        return [src for _, src in scored]

    def _compute_score(self, source: dict[str, Any]) -> float:
        """Compute composite credibility score in [0, 1]."""
        url = source.get("url", "")
        domain = self._extract_domain(url)

        # Base domain authority
        domain_auth = self._domain_authority(domain)

        # Recency (newer is better)
        recency = self._recency_score(source.get("published_at"), source.get("retrieved_at"))

        # Bias penalty
        bias = self._bias_penalty(domain, source.get("title", ""), source.get("content", ""))

        # Cross-reference bonus
        cross_refs = source.get("cross_reference_count", 0)
        cross_ref_bonus = min(cross_refs * 0.05, 0.15)

        # Source type weight
        type_weight = self._source_type_weight(source.get("source_type", "news"))

        composite = (domain_auth * 0.35 + recency * 0.20 + type_weight * 0.25 + cross_ref_bonus) - bias
        return max(0.0, min(1.0, composite))

    def _extract_domain(self, url: str | None) -> str:
        if not url:
            return ""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip("www.")

    def _domain_authority(self, domain: str) -> float:
        # Exact match
        if domain in self.DOMAIN_AUTHORITY_MAP:
            return self.DOMAIN_AUTHORITY_MAP[domain]
        # TLD match (e.g., .gov)
        for suffix, score in self.DOMAIN_AUTHORITY_MAP.items():
            if domain.endswith(suffix):
                return score
        # Default
        return 0.50

    def _recency_score(self, published_at: str | None, retrieved_at: str | None) -> float:
        """Score recency: 1.0 for today, decaying over time."""
        if not published_at and not retrieved_at:
            return 0.5
        try:
            from datetime import datetime, timezone
            ts_str = published_at or retrieved_at or ""
            # Handle common formats
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            else:
                return 0.5
            days_old = (datetime.now(timezone.utc) - dt).days
            if days_old <= 0:
                return 1.0
            if days_old <= 7:
                return 0.9
            if days_old <= 30:
                return 0.75
            if days_old <= 90:
                return 0.6
            if days_old <= 365:
                return 0.4
            return 0.2
        except Exception:
            return 0.5

    def _bias_penalty(self, domain: str, title: str, content: str) -> float:
        """Detect bias indicators and return penalty in [0, 0.5]."""
        penalty = 0.0
        text = f"{domain} {title} {content}".lower()
        for pattern in self.BIAS_DOMAIN_PATTERNS:
            if pattern in text:
                penalty += 0.15
        # Sensationalism heuristic
        sensational_words = ["shocking", "unbelievable", "you won't believe", "miracle", "doctors hate"]
        for word in sensational_words:
            if word in text:
                penalty += 0.05
        return min(0.5, penalty)

    def _source_type_weight(self, source_type: str) -> float:
        weights = {
            "academic": 0.95,
            "government": 0.90,
            "industry": 0.70,
            "news": 0.65,
            "blog": 0.40,
            "social": 0.20,
        }
        return weights.get(source_type, 0.50)
