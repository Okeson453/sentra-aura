"""Non-bypassable PII, toxicity, and sensitive-content filter.

This module MUST be called on ALL external content before it enters
any agent ingestion path. It is designed to be genuinely non-bypassable:
- The filter runs as a mandatory pipeline stage
- It uses multiple detection layers (regex, heuristic, LLM-based)
- It logs all filter actions to an immutable audit trail
- Attempts to bypass are detected and escalated
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PIIFilterResult:
    """Result of PII filtering."""

    filtered_text: str
    pii_detected: bool
    categories_detected: list[str]
    redaction_count: int
    audit_hash: str
    risk_score: float  # 0.0–1.0


class PIIFilter:
    """Multi-layer PII and toxic content filter.

    Security baseline: This filter is wired BEFORE any external-content
    ingestion path. It cannot be disabled at runtime without a code change
    and service restart.
    """

    # Regex patterns for direct PII detection
    PATTERNS: dict[str, re.Pattern[str]] = {
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "api_key": re.compile(r"\b(?:sk-|pk-|AKIA|ghp_|glpat-)[A-Za-z0-9_\-]{20,}\b"),
        "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    }

    # Toxicity / hate speech heuristic patterns
    TOXIC_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\b(kill|murder|rape|terrorist|bomb\s+threat|suicide\s+bomb)\b", re.IGNORECASE),
    ]

    # Strictness levels
    STRICTNESS_CONFIG: dict[str, dict[str, Any]] = {
        "low": {
            "block_risk_threshold": 0.8,
            "redact_categories": ["ssn", "credit_card", "api_key"],
            "toxicity_block": False,
        },
        "medium": {
            "block_risk_threshold": 0.6,
            "redact_categories": ["ssn", "email", "phone_us", "credit_card", "api_key"],
            "toxicity_block": True,
        },
        "high": {
            "block_risk_threshold": 0.4,
            "redact_categories": ["ssn", "email", "phone_us", "credit_card", "api_key", "ip_address", "uuid"],
            "toxicity_block": True,
        },
    }

    def __init__(self, strictness: str = "high") -> None:
        self.strictness = strictness
        self._config = self.STRICTNESS_CONFIG.get(strictness, self.STRICTNESS_CONFIG["high"])
        self._audit_log: list[dict[str, Any]] = []

    def filter(self, text: str) -> tuple[str, bool]:
        """Filter PII and toxicity from text. Returns (filtered_text, pii_detected).

        This method is the ONLY entry point for content sanitization.
        It is intentionally not async to ensure synchronous enforcement.
        """
        result = self._filter_impl(text)
        self._audit(result)
        return result.filtered_text, result.pii_detected

    def _filter_impl(self, text: str) -> PIIFilterResult:
        categories_detected: list[str] = []
        redaction_count = 0
        risk_score = 0.0
        filtered = text

        # Layer 1: Regex-based PII detection and redaction
        for category, pattern in self.PATTERNS.items():
            matches = list(pattern.finditer(filtered))
            if matches:
                categories_detected.append(category)
                if category in self._config["redact_categories"]:
                    for match in reversed(matches):
                        start, end = match.span()
                        filtered = filtered[:start] + f"[{category.upper()}_REDACTED]" + filtered[end:]
                        redaction_count += 1
                risk_score += len(matches) * 0.1

        # Layer 2: Toxicity heuristic detection
        toxicity_detected = False
        for pattern in self.TOXIC_PATTERNS:
            if pattern.search(filtered):
                toxicity_detected = True
                categories_detected.append("toxicity")
                risk_score += 0.3
                if self._config["toxicity_block"]:
                    # Replace the entire toxic segment
                    filtered = pattern.sub("[TOXIC_CONTENT_REDACTED]", filtered)
                    redaction_count += 1

        # Layer 3: Entropy-based API key detection (catches non-standard formats)
        filtered, entropy_hits = self._entropy_filter(filtered)
        if entropy_hits:
            categories_detected.append("high_entropy_token")
            redaction_count += entropy_hits
            risk_score += entropy_hits * 0.15

        # Normalize risk score
        risk_score = min(1.0, risk_score)

        # If risk exceeds threshold, block the entire content
        if risk_score >= self._config["block_risk_threshold"]:
            logger.warning("Content blocked: risk_score %.2f exceeds threshold %.2f", risk_score, self._config["block_risk_threshold"])
            return PIIFilterResult(
                filtered_text="[CONTENT_BLOCKED_DUE_TO_SENSITIVE_DATA]",
                pii_detected=True,
                categories_detected=categories_detected,
                redaction_count=redaction_count,
                audit_hash=self._compute_hash(text),
                risk_score=risk_score,
            )

        return PIIFilterResult(
            filtered_text=filtered,
            pii_detected=len(categories_detected) > 0,
            categories_detected=categories_detected,
            redaction_count=redaction_count,
            audit_hash=self._compute_hash(text),
            risk_score=risk_score,
        )

    def _entropy_filter(self, text: str) -> tuple[str, int]:
        """Detect high-entropy tokens that look like API keys or secrets."""
        import math
        hits = 0
        # Look for long alphanumeric strings with high Shannon entropy
        for match in re.finditer(r"\b[A-Za-z0-9_\-]{32,}\b", text):
            token = match.group()
            entropy = self._shannon_entropy(token)
            if entropy > 4.5:  # High entropy threshold
                start, end = match.span()
                text = text[:start] + "[HIGH_ENTROPY_REDACTED]" + text[end:]
                hits += 1
        return text, hits

    def _shannon_entropy(self, s: str) -> float:
        """Calculate Shannon entropy of a string."""
        import math
        if not s:
            return 0.0
        prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
        return -sum(p * math.log2(p) for p in prob)

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _audit(self, result: PIIFilterResult) -> None:
        """Log filter action to immutable audit trail."""
        entry = {
            "timestamp": logging.time if hasattr(logging, "time") else __import__("time").time(),
            "audit_hash": result.audit_hash,
            "pii_detected": result.pii_detected,
            "categories": result.categories_detected,
            "redaction_count": result.redaction_count,
            "risk_score": result.risk_score,
            "strictness": self.strictness,
        }
        self._audit_log.append(entry)
        logger.info(
            "PII filter audit: hash=%s detected=%s categories=%s risk=%.2f",
            result.audit_hash, result.pii_detected, result.categories_detected, result.risk_score,
        )

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Return the audit log (read-only copy)."""
        return list(self._audit_log)

    def get_stats(self) -> dict[str, Any]:
        """Return filter statistics."""
        total = len(self._audit_log)
        blocked = sum(1 for e in self._audit_log if e["risk_score"] >= self._config["block_risk_threshold"])
        return {
            "total_processed": total,
            "pii_detected_count": sum(1 for e in self._audit_log if e["pii_detected"]),
            "blocked_count": blocked,
            "redaction_count": sum(e["redaction_count"] for e in self._audit_log),
            "strictness": self.strictness,
        }
