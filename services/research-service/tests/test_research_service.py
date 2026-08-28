"""Tests for Research Service components."""

from __future__ import annotations

import pytest

from research_service.config import ResearchConfig
from research_service.retrieval.ranker import SourceRanker
from research_service.pii_filter import PIIFilter
from research_service.claim_extraction import ClaimExtractor


@pytest.fixture
def config() -> ResearchConfig:
    return ResearchConfig(
        provider_gateway_url="http://localhost:8000",
        provider_gateway_api_key="test-key",
        pii_filter_enabled=True,
        pii_filter_strictness="high",
        claim_extraction_min_confidence=0.5,
    )


class TestSourceRanker:
    def test_rank_by_domain_authority(self, config: ResearchConfig) -> None:
        ranker = SourceRanker(config)
        sources = [
            {"url": "https://example.com/blog/post", "title": "Random blog", "source_type": "blog"},
            {"url": "https://nature.com/article/123", "title": "Nature article", "source_type": "academic"},
            {"url": "https://reuters.com/news/456", "title": "Reuters news", "source_type": "news"},
        ]
        ranked = ranker.rank(sources)
        assert ranked[0]["url"] == "https://nature.com/article/123"
        assert ranked[0]["credibility_score"] > ranked[1]["credibility_score"]

    def test_rank_with_recency(self, config: ResearchConfig) -> None:
        ranker = SourceRanker(config)
        sources = [
            {"url": "https://example.com/old", "title": "Old news", "published_at": "2020-01-01", "source_type": "news"},
            {"url": "https://example.com/new", "title": "New news", "published_at": "2026-08-16", "source_type": "news"},
        ]
        ranked = ranker.rank(sources)
        assert ranked[0]["url"] == "https://example.com/new"

    def test_bias_penalty(self, config: ResearchConfig) -> None:
        ranker = SourceRanker(config)
        sources = [
            {"url": "https://example.com/fair", "title": "Balanced report", "source_type": "news"},
            {"url": "https://clickbait.example.com", "title": "Shocking unbelievable miracle", "source_type": "blog"},
        ]
        ranked = ranker.rank(sources)
        assert ranked[0]["url"] == "https://example.com/fair"
        assert ranked[1]["credibility_score"] < 0.5

    def test_deduplication_preserved(self, config: ResearchConfig) -> None:
        ranker = SourceRanker(config)
        sources = [
            {"url": "https://example.com/a", "title": "A", "source_type": "news"},
            {"url": "https://example.com/a", "title": "A duplicate", "source_type": "news"},
            {"url": "https://example.com/b", "title": "B", "source_type": "news"},
        ]
        ranked = ranker.rank(sources)
        urls = [r["url"] for r in ranked]
        assert urls.count("https://example.com/a") == 1


class TestPIIFilter:
    def test_filter_ssn(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "My SSN is 123-45-6789 and my email is john@example.com"
        filtered, detected = pii.filter(text)
        assert detected is True
        assert "[SSN_REDACTED]" in filtered
        assert "[EMAIL_REDACTED]" in filtered
        assert "123-45-6789" not in filtered
        assert "john@example.com" not in filtered

    def test_filter_credit_card(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "Card: 4111-1111-1111-1111"
        filtered, detected = pii.filter(text)
        assert detected is True
        assert "[CREDIT_CARD_REDACTED]" in filtered

    def test_filter_api_key(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "sk-abcdefghijklmnopqrstuvwxyz1234567890abcdef"
        filtered, detected = pii.filter(text)
        assert detected is True
        assert "[API_KEY_REDACTED]" in filtered

    def test_filter_toxicity(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "This is a bomb threat against the building"
        filtered, detected = pii.filter(text)
        assert detected is True
        assert "[TOXIC_CONTENT_REDACTED]" in filtered

    def test_filter_no_pii(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "Quantum computing uses qubits to perform calculations."
        filtered, detected = pii.filter(text)
        assert detected is False
        assert filtered == text

    def test_filter_high_entropy_token(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        text = "Token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
        filtered, detected = pii.filter(text)
        assert detected is True
        assert "[HIGH_ENTROPY_REDACTED]" in filtered

    def test_filter_strictness_levels(self, config: ResearchConfig) -> None:
        low = PIIFilter(strictness="low")
        high = PIIFilter(strictness="high")
        text = "Contact me at user@example.com"
        low_filtered, low_detected = low.filter(text)
        high_filtered, high_detected = high.filter(text)
        assert low_detected is True  # email detected at all levels
        assert high_detected is True
        assert "[EMAIL_REDACTED]" in high_filtered

    def test_audit_log(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        pii.filter("SSN: 123-45-6789")
        log = pii.get_audit_log()
        assert len(log) == 1
        assert log[0]["pii_detected"] is True
        assert "ssn" in log[0]["categories"]

    def test_stats(self, config: ResearchConfig) -> None:
        pii = PIIFilter(strictness="high")
        pii.filter("Safe text")
        pii.filter("SSN: 123-45-6789")
        stats = pii.get_stats()
        assert stats["total_processed"] == 2
        assert stats["pii_detected_count"] == 1
        assert stats["strictness"] == "high"


class TestClaimExtractor:
    def test_extract_numerical_claims(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.5)
        text = "In 2024, global temperatures rose by 1.2 degrees. The study found that 85% of glaciers are retreating."
        claims = extractor.extract(text)
        assert len(claims) >= 2
        assert any("2024" in c.text for c in claims)
        assert any("85%" in c.text for c in claims)

    def test_extract_pattern_claims(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.5)
        text = "According to NASA, the ozone layer is recovering. Research shows that CFC emissions have declined."
        claims = extractor.extract(text)
        assert any("NASA" in c.text for c in claims)
        assert any("Research shows" in c.text for c in claims)

    def test_confidence_scoring(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.5)
        text = "It is confirmed that vaccines prevent disease. This is possibly maybe true."
        claims = extractor.extract(text)
        confirmed = [c for c in claims if "confirmed" in c.text.lower()]
        hedged = [c for c in claims if "possibly" in c.text.lower()]
        if confirmed:
            assert confirmed[0].confidence > 0.6
        if hedged:
            assert hedged[0].confidence < 0.6

    def test_min_confidence_filter(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.8)
        text = "The sky is blue. Water is wet."
        claims = extractor.extract(text)
        # These simple claims should score below 0.8
        assert len(claims) == 0

    def test_link_to_sources(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.5)
        claims = [
            extractor.Claim(
                claim_id="c1",
                text="The Earth orbits the Sun",
                confidence=0.9,
            )
        ]
        sources = [
            {"source_id": "s1", "title": "Earth orbits Sun", "content": "The Earth orbits the Sun every 365 days", "credibility_score": 0.9},
        ]
        linked = extractor.link_to_sources(claims, sources)
        assert "s1" in linked[0].source_ids
        assert linked[0].verified is True
        assert linked[0].verification_status == "verified"

    def test_deduplication(self, config: ResearchConfig) -> None:
        extractor = ClaimExtractor(min_confidence=0.5)
        text = "The Earth orbits the Sun. The Earth orbits the Sun."
        claims = extractor.extract(text)
        # Should deduplicate identical claims
        texts = [c.text for c in claims]
        assert len(texts) == len(set(texts))
