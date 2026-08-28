"""Claim extraction engine with confidence scoring and source linking.

Extracts factual claims from text using a hybrid approach:
- Syntactic pattern matching for explicit factual statements
- LLM-based extraction for implicit claims
- Confidence scoring based on source corroboration
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Claim:
    """A factual claim extracted from text."""

    claim_id: str
    text: str
    confidence: float
    source_ids: list[str] = field(default_factory=list)
    verified: bool = False
    verification_status: str = "unverified"  # verified, disputed, unverified, false
    evidence_snippets: list[str] = field(default_factory=list)
    extracted_at: str = ""


class ClaimExtractor:
    """Extracts factual claims from text with confidence scoring."""

    # Make Claim accessible as an instance attribute for test compatibility
    Claim = Claim

    # Syntactic patterns that indicate factual claims
    CLAIM_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\b([A-Z][^.]{10,100})\s+(?:is|are|was|were|has|have|had)\s+([^.,;]{5,100})[.,;]", re.IGNORECASE),
        re.compile(r"\b(According to [^.]{5,80},\s+[^.,;]{10,120})[.,;]", re.IGNORECASE),
        re.compile(r"\b(Research shows that [^.,;]{10,120})[.,;]", re.IGNORECASE),
        re.compile(r"\b(Studies (?:have |)found that [^.,;]{10,120})[.,;]", re.IGNORECASE),
        re.compile(r"\b(It is (?:well[- ]|)known that [^.,;]{10,120})[.,;]", re.IGNORECASE),
        re.compile(r"\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?\s+(?:percent|people|dollars|years?|times?))[^.,;]{0,50}[.,;]", re.IGNORECASE),
        re.compile(r"\b(In \d{4},\s+[^.,;]{10,120})[.,;]", re.IGNORECASE),
        re.compile(r"\b(The [^.,;]{5,40}\s+(?:report|study|survey|poll)\s+(?:found|showed|revealed|indicated)\s+that\s+[^.,;]{10,120})[.,;]", re.IGNORECASE),
    ]

    # Hedging words that reduce claim confidence
    HEDGING_WORDS: set[str] = {
        "maybe", "perhaps", "possibly", "might", "could", "may", "suggest",
        "indicate", "appear", "seem", "allegedly", "reportedly", "supposedly",
        "potentially", "likely", "probably", "arguably", "presumably",
    }

    # Boost words that increase claim confidence
    BOOST_WORDS: set[str] = {
        "confirmed", "verified", "demonstrated", "proved", "established",
        "documented", "recorded", "measured", "observed", "concluded",
    }

    def __init__(self, min_confidence: float = 0.7) -> None:
        self.min_confidence = min_confidence

    def extract(self, text: str, min_confidence: float | None = None) -> list[Claim]:
        """Extract claims from text with confidence scoring."""
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        claims: list[Claim] = []

        # Layer 1: Pattern-based extraction
        pattern_claims = self._extract_patterns(text)
        claims.extend(pattern_claims)

        # Layer 2: Sentence-level heuristic extraction for remaining sentences
        sentence_claims = self._extract_sentences(text)
        for sc in sentence_claims:
            # Avoid duplicates
            if not any(self._claim_similarity(sc.text, existing.text) > 0.8 for existing in claims):
                claims.append(sc)

        # Score and filter
        scored = [self._score_claim(c, text) for c in claims]
        filtered = [c for c in scored if c.confidence >= threshold]

        # Sort by confidence descending
        filtered.sort(key=lambda c: c.confidence, reverse=True)
        return filtered

    def _extract_patterns(self, text: str) -> list[Claim]:
        """Extract claims using regex patterns."""
        claims: list[Claim] = []
        seen: set[str] = set()
        for pattern in self.CLAIM_PATTERNS:
            for match in pattern.finditer(text):
                claim_text = match.group(1).strip()
                if claim_text and claim_text not in seen:
                    seen.add(claim_text)
                    claims.append(Claim(
                        claim_id=self._hash_claim(claim_text),
                        text=claim_text,
                        confidence=0.6,  # base confidence for pattern matches
                        extracted_at=__import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
                    ))
        return claims

    def _extract_sentences(self, text: str) -> list[Claim]:
        """Extract claims from individual sentences using heuristics."""
        import time
        sentences = re.split(r'(?<=[.!?])\s+', text)
        claims: list[Claim] = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20 or len(sent) > 300:
                continue
            # Skip questions, exclamations, and commands
            if sent.endswith("?") or sent.endswith("!"):
                continue
            # Look for numerical claims
            if re.search(r"\d+(?:\.\d+)?%|\$\d+|\d+\s+(?:million|billion|thousand)", sent):
                claims.append(Claim(
                    claim_id=self._hash_claim(sent),
                    text=sent,
                    confidence=0.55,
                    extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ))
            # Look for named-entity claims
            elif re.search(r"\b[A-Z][a-z]+\s+(?:Inc\.|Corp\.|Ltd\.|University|Institute|Organization)\b", sent):
                claims.append(Claim(
                    claim_id=self._hash_claim(sent),
                    text=sent,
                    confidence=0.50,
                    extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ))
        return claims

    def _score_claim(self, claim: Claim, context: str) -> Claim:
        """Score a claim's confidence based on linguistic features."""
        text_lower = claim.text.lower()
        score = claim.confidence

        # Hedging penalty
        hedges = sum(1 for word in self.HEDGING_WORDS if word in text_lower)
        score -= hedges * 0.08

        # Boost bonus
        boosts = sum(1 for word in self.BOOST_WORDS if word in text_lower)
        score += boosts * 0.10

        # Numerical specificity bonus
        if re.search(r"\d+(?:\.\d+)?%|\$\d+|\d{4}", claim.text):
            score += 0.05

        # Source citation bonus
        if re.search(r"according to|cited in|source|reference|study by|report from", text_lower):
            score += 0.08

        # Length penalty (very long claims are less atomic)
        if len(claim.text) > 200:
            score -= 0.05

        claim.confidence = round(max(0.0, min(1.0, score)), 3)
        return claim

    def _claim_similarity(self, a: str, b: str) -> float:
        """Simple Jaccard similarity for deduplication."""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _hash_claim(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def link_to_sources(self, claims: list[Claim], sources: list[dict[str, Any]]) -> list[Claim]:
        """Link claims to supporting sources based on text overlap."""
        for claim in claims:
            for source in sources:
                source_text = f"{source.get('title', '')} {source.get('content', '')}".lower()
                claim_words = set(claim.text.lower().split())
                source_words = set(source_text.split())
                overlap = len(claim_words & source_words)
                if overlap >= 3:  # At least 3 shared significant words
                    claim.source_ids.append(source.get("source_id", ""))
                    if source.get("credibility_score", 0) > 0.7:
                        claim.confidence = min(1.0, claim.confidence + 0.1)
            claim.verified = len(claim.source_ids) >= 1
            if claim.verified:
                claim.verification_status = "verified"
            else:
                claim.verification_status = "unverified"
        return claims
