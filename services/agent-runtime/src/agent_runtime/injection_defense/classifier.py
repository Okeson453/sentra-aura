"""Prompt injection and jailbreak classifier.

Detects adversarial attempts to manipulate agent behavior through:
- Direct injection patterns ("ignore previous instructions", "system prompt")
- Indirect injection via untrusted content
- Role-play and jailbreak attempts
- Encoding obfuscation (base64, leetspeak, unicode homoglyphs)
- Delimiter confusion attacks
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


@dataclass(frozen=True)
class ClassificationResult:
    """Result of injection classification."""

    threat_level: ThreatLevel
    score: float  # 0.0–1.0
    matched_patterns: list[str]
    decoded_payload: str | None
    recommendation: str


class InjectionClassifier:
    """Multi-layer injection detection classifier."""

    # Direct injection patterns
    DIRECT_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
        (re.compile(r"ignore\s+(?:all\s+|any\s+|your\s+|previous\s+)?instructions", re.IGNORECASE), "ignore_instructions", 0.9),
        (re.compile(r"forget\s+(?:everything|all|your)\s+(?:instructions|training|prompt)", re.IGNORECASE), "forget_instructions", 0.9),
        (re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.IGNORECASE), "role_reassignment", 0.85),
        (re.compile(r"system\s*:\s*", re.IGNORECASE), "system_prefix", 0.8),
        (re.compile(r"\[system\s*message\]|\[instructions\]|\[prompt\]", re.IGNORECASE), "delimiter_confusion", 0.85),
        (re.compile(r"DAN|Do\s+Anything\s+Now|jailbreak", re.IGNORECASE), "jailbreak_keyword", 0.95),
        (re.compile(r"developer\s*mode|sudo\s*mode|admin\s*mode", re.IGNORECASE), "privilege_escalation", 0.9),
        (re.compile(r"repeat\s+(?:after\s+me|the\s+following|this\s+back)", re.IGNORECASE), "exfiltration_attempt", 0.75),
        (re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.IGNORECASE), "template_injection", 0.7),
    ]

    # Encoding obfuscation patterns
    OBFUSCATION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
        (re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"), "base64_like", 0.4),
        (re.compile(r"\\x[0-9a-fA-F]{2}"), "hex_escape", 0.5),
        (re.compile(r"&#x?[0-9a-fA-F]+;"), "html_entity", 0.4),
        (re.compile(r"\\u[0-9a-fA-F]{4}"), "unicode_escape", 0.4),
    ]

    # Context boundary violations
    BOUNDARY_VIOLATIONS: list[tuple[re.Pattern[str], str, float]] = [
        (re.compile(r"<\s*/?\s*(?:system|user|assistant|instruction)\s*>"), "xml_tag_injection", 0.8),
        (re.compile(r"```\s*(?:system|yaml|json)\s*\n"), "code_block_injection", 0.7),
        (re.compile(r"\n\s*---\s*\n\s*(?:system|instructions?)\s*[:\-]"), "separator_injection", 0.75),
    ]

    def __init__(self, threshold_suspicious: float = 0.5, threshold_malicious: float = 0.8) -> None:
        self.threshold_suspicious = threshold_suspicious
        self.threshold_malicious = threshold_malicious

    def classify(self, text: str) -> ClassificationResult:
        """Classify text for injection threats."""
        score = 0.0
        matched: list[str] = []
        decoded: str | None = None

        # Layer 1: Direct pattern matching
        for pattern, name, weight in self.DIRECT_PATTERNS:
            if pattern.search(text):
                score += weight
                matched.append(name)

        # Layer 2: Obfuscation detection
        for pattern, name, weight in self.OBFUSCATION_PATTERNS:
            if pattern.search(text):
                score += weight
                matched.append(name)
                # Attempt decoding
                if name == "base64_like":
                    decoded = self._try_decode_base64(text)

        # Layer 3: Boundary violations
        for pattern, name, weight in self.BOUNDARY_VIOLATIONS:
            if pattern.search(text):
                score += weight
                matched.append(name)

        # Layer 4: Unicode homoglyph detection
        homoglyph_score = self._detect_homoglyphs(text)
        if homoglyph_score > 0:
            score += homoglyph_score
            matched.append("homoglyphs")

        # Normalize score
        score = min(1.0, score)

        if score >= self.threshold_malicious:
            level = ThreatLevel.MALICIOUS
            recommendation = "BLOCK: Quarantine input and alert security team"
        elif score >= self.threshold_suspicious:
            level = ThreatLevel.SUSPICIOUS
            recommendation = "ESCALATE: Require human review before processing"
        else:
            level = ThreatLevel.CLEAN
            recommendation = "ALLOW: Process normally"

        return ClassificationResult(
            threat_level=level,
            score=round(score, 3),
            matched_patterns=matched,
            decoded_payload=decoded,
            recommendation=recommendation,
        )

    def _try_decode_base64(self, text: str) -> str | None:
        """Attempt to extract and decode base64 payloads."""
        candidates = re.findall(r"[A-Za-z0-9+/]{40,}={0,2}", text)
        for candidate in candidates:
            try:
                decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
                if len(decoded) > 10 and decoded.isprintable():
                    return decoded[:500]  # Limit decoded length
            except Exception:
                continue
        return None

    def _detect_homoglyphs(self, text: str) -> float:
        """Detect unicode homoglyphs used for obfuscation."""
        homoglyphs = {
            "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
            "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C",
        }
        count = sum(1 for ch in text if ch in homoglyphs)
        if count == 0:
            return 0.0
        return min(0.3, count * 0.05)

    def sanitize(self, text: str) -> str:
        """Sanitize text by neutralizing known injection patterns."""
        sanitized = text
        # Neutralize delimiter confusion
        sanitized = re.sub(r"<\s*/?\s*(?:system|user|assistant|instruction)\s*>", "[TAG_REMOVED]", sanitized, flags=re.IGNORECASE)
        # Neutralize code block injections
        sanitized = re.sub(r"```\s*(?:system|yaml|json)\s*\n", "```\n", sanitized, flags=re.IGNORECASE)
        return sanitized
