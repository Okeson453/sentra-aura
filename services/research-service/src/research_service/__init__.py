"""SentraAura Research Service — deep research, source credibility scoring, fact-checking, claim extraction."""

__version__ = "1.0.0"

from research_service.retrieval.engine import RetrievalEngine
from research_service.retrieval.ranker import SourceRanker
from research_service.pii_filter import PIIFilter
from research_service.claim_extraction import ClaimExtractor

__all__ = ["RetrievalEngine", "SourceRanker", "PIIFilter", "ClaimExtractor"]
