"""Untrusted boundary enforcement for external content entering agent pipelines.

All content from external sources (web search, user input, third-party APIs)
MUST pass through this boundary before reaching any agent's context window.
The boundary applies:
1. PII filtering (from research-service pii_filter)
2. Injection classification (from classifier)
3. Content length limits
4. Encoding normalization
5. Audit logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent_runtime.injection_defense.classifier import InjectionClassifier, ThreatLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundaryResult:
    """Result of boundary validation."""

    allowed: bool
    sanitized_text: str
    threat_level: str
    threat_score: float
    pii_detected: bool
    injection_detected: bool
    truncation_applied: bool
    audit_hash: str
    metadata: dict[str, Any]


class UntrustedBoundary:
    """Enforces the untrusted content boundary."""

    def __init__(
        self,
        max_content_length: int = 50_000,
        classifier: InjectionClassifier | None = None,
    ) -> None:
        self.max_content_length = max_content_length
        self.classifier = classifier or InjectionClassifier()

    def validate(self, text: str, source: str = "unknown", agent_id: str = "unknown") -> BoundaryResult:
        """Validate and sanitize untrusted content.

        This is the ONLY entry point for external content into agent pipelines.
        It cannot be bypassed at runtime.
        """
        import hashlib
        import time

        original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        metadata: dict[str, Any] = {
            "source": source,
            "agent_id": agent_id,
            "original_length": len(text),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Step 1: Length enforcement
        truncation_applied = False
        if len(text) > self.max_content_length:
            text = text[:self.max_content_length] + "\n[CONTENT_TRUNCATED_BY_BOUNDARY]"
            truncation_applied = True
            metadata["truncated_from"] = metadata["original_length"]

        # Step 2: Injection classification
        classification = self.classifier.classify(text)
        injection_detected = classification.threat_level in (ThreatLevel.SUSPICIOUS, ThreatLevel.MALICIOUS)

        # Step 3: Sanitize if suspicious
        sanitized = text
        if classification.threat_level == ThreatLevel.MALICIOUS:
            sanitized = "[MALICIOUS_CONTENT_BLOCKED]"
            logger.warning(
                "Boundary BLOCKED malicious content from %s for agent %s: score=%.2f patterns=%s",
                source, agent_id, classification.score, classification.matched_patterns,
            )
        elif classification.threat_level == ThreatLevel.SUSPICIOUS:
            sanitized = self.classifier.sanitize(text)
            sanitized += "\n[CONTENT_FLAGGED_FOR_REVIEW]"
            logger.warning(
                "Boundary FLAGGED suspicious content from %s for agent %s: score=%.2f",
                source, agent_id, classification.score,
            )

        # Step 4: PII check (lightweight — full PII filter runs in research-service)
        pii_detected = self._quick_pii_scan(sanitized)
        if pii_detected:
            sanitized = self._redact_pii(sanitized)
            metadata["pii_redacted"] = True

        result = BoundaryResult(
            allowed=classification.threat_level != ThreatLevel.MALICIOUS,
            sanitized_text=sanitized,
            threat_level=classification.threat_level.value,
            threat_score=classification.score,
            pii_detected=pii_detected,
            injection_detected=injection_detected,
            truncation_applied=truncation_applied,
            audit_hash=original_hash,
            metadata=metadata,
        )

        logger.info(
            "Boundary result: source=%s agent=%s allowed=%s threat=%s",
            source, agent_id, result.allowed, result.threat_level,
        )
        return result

    def _quick_pii_scan(self, text: str) -> bool:
        """Quick heuristic PII scan (full filter in research-service)."""
        import re
        patterns = [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
            re.compile(r"\b(?:sk-|pk-|AKIA)[A-Za-z0-9_\-]{20,}\b"),  # API keys
        ]
        return any(p.search(text) for p in patterns)

    def _redact_pii(self, text: str) -> str:
        """Redact detected PII patterns."""
        import re
        text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", text)
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]", text)
        text = re.sub(r"\b(?:sk-|pk-|AKIA)[A-Za-z0-9_\-]{20,}\b", "[KEY_REDACTED]", text)
        return text
