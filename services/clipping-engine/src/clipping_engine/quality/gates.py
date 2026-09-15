"""Architecture §9 quality gates — implementable checks without heavy ML deps.

Gates that require external models (CLIP, NLI) report mode=deferred with
a fail-closed option for production policy.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    gate_id: str
    passed: bool
    score: float
    mode: str  # measured | heuristic | deferred
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""


def run_audio_quality_gate(
    *,
    snr_db: float | None = None,
    duration_seconds: float | None = None,
    min_snr_db: float = 25.0,
) -> GateResult:
    """Audio quality gate (SNR > 25dB when measured)."""
    if snr_db is None:
        return GateResult(
            gate_id="audio_quality",
            passed=True,
            score=0.5,
            mode="deferred",
            message="SNR not measured; gate deferred (not fail-closed by default)",
            details={"min_snr_db": min_snr_db},
        )
    passed = snr_db >= min_snr_db
    return GateResult(
        gate_id="audio_quality",
        passed=passed,
        score=min(1.0, max(0.0, snr_db / (min_snr_db * 1.5))),
        mode="measured",
        details={"snr_db": snr_db, "min_snr_db": min_snr_db, "duration_seconds": duration_seconds},
        message="ok" if passed else f"SNR {snr_db:.1f}dB below {min_snr_db}dB",
    )


def run_provenance_gate(
    *,
    source_asset_ids: list[str] | None = None,
    rights_cleared: bool | None = None,
    require_rights: bool = True,
) -> GateResult:
    """Copyright / provenance gate — requires lineage ids and optional rights flag."""
    sources = source_asset_ids or []
    if not sources:
        return GateResult(
            gate_id="copyright_provenance",
            passed=False,
            score=0.0,
            mode="heuristic",
            message="No source_asset_ids — fail closed",
            details={"source_count": 0},
        )
    if require_rights and rights_cleared is False:
        return GateResult(
            gate_id="copyright_provenance",
            passed=False,
            score=0.2,
            mode="heuristic",
            message="Rights not cleared",
            details={"source_asset_ids": sources, "rights_cleared": rights_cleared},
        )
    return GateResult(
        gate_id="copyright_provenance",
        passed=True,
        score=1.0 if rights_cleared else 0.7,
        mode="heuristic",
        details={"source_asset_ids": sources, "rights_cleared": rights_cleared},
        message="ok",
    )


def run_factual_accuracy_gate(
    *,
    claims: list[str] | None = None,
    verified_ratio: float | None = None,
) -> GateResult:
    """Factual accuracy gate — uses provided verified_ratio or heuristic claim scan."""
    if verified_ratio is not None:
        passed = verified_ratio >= 0.8
        return GateResult(
            gate_id="factual_accuracy",
            passed=passed,
            score=verified_ratio,
            mode="measured",
            details={"verified_ratio": verified_ratio, "claim_count": len(claims or [])},
            message="ok" if passed else "verified_ratio below 0.8",
        )
    claims = claims or []
    if not claims:
        return GateResult(
            gate_id="factual_accuracy",
            passed=True,
            score=0.6,
            mode="deferred",
            message="No claims supplied; deferred",
        )
    # Heuristic: flag absolute superlatives / unsourced numbers as risk
    risk = 0
    for c in claims:
        if re.search(r"\b(always|never|100%|guaranteed)\b", c, re.I):
            risk += 1
        if re.search(r"\b\d{2,}%\b", c) and "source" not in c.lower():
            risk += 1
    ratio = max(0.0, 1.0 - risk / max(len(claims), 1))
    return GateResult(
        gate_id="factual_accuracy",
        passed=ratio >= 0.7,
        score=ratio,
        mode="heuristic",
        details={"claim_count": len(claims), "risk_flags": risk},
        message="ok" if ratio >= 0.7 else "heuristic risk flags elevated",
    )


def run_hallucination_gate(
    *,
    generated_text: str = "",
    source_texts: list[str] | None = None,
    min_overlap: float = 0.05,
) -> GateResult:
    """Hallucination gate — token overlap vs sources (NLI deferred)."""
    if not generated_text.strip():
        return GateResult(
            gate_id="hallucination",
            passed=True,
            score=1.0,
            mode="heuristic",
            message="empty generation",
        )
    sources = source_texts or []
    if not sources:
        return GateResult(
            gate_id="hallucination",
            passed=False,
            score=0.3,
            mode="heuristic",
            message="No source_texts — cannot ground generation (fail soft)",
            details={"generated_len": len(generated_text)},
        )
    gen_tokens = set(re.findall(r"[a-z0-9]+", generated_text.lower()))
    src_tokens: set[str] = set()
    for s in sources:
        src_tokens |= set(re.findall(r"[a-z0-9]+", s.lower()))
    if not gen_tokens:
        return GateResult(gate_id="hallucination", passed=True, score=1.0, mode="heuristic")
    overlap = len(gen_tokens & src_tokens) / len(gen_tokens)
    passed = overlap >= min_overlap
    return GateResult(
        gate_id="hallucination",
        passed=passed,
        score=min(1.0, overlap * 2),
        mode="heuristic",
        details={"token_overlap": round(overlap, 4), "min_overlap": min_overlap},
        message="ok" if passed else f"token overlap {overlap:.3f} < {min_overlap}",
    )


def run_visual_relevance_gate(
    *,
    clip_score: float | None = None,
    min_score: float = 0.25,
) -> GateResult:
    """Visual relevance (CLIP) — uses provided score; model load deferred."""
    if clip_score is None:
        return GateResult(
            gate_id="visual_relevance",
            passed=True,
            score=0.5,
            mode="deferred",
            message="CLIP score not provided; deferred",
            details={"min_score": min_score},
        )
    passed = clip_score >= min_score
    return GateResult(
        gate_id="visual_relevance",
        passed=passed,
        score=max(0.0, min(1.0, clip_score)),
        mode="measured",
        details={"clip_score": clip_score, "min_score": min_score},
        message="ok" if passed else f"clip_score {clip_score} < {min_score}",
    )


def run_all_gates(**kwargs: Any) -> dict[str, Any]:
    """Run the standard gate set; returns aggregate pass/fail."""
    results = [
        run_audio_quality_gate(
            snr_db=kwargs.get("snr_db"),
            duration_seconds=kwargs.get("duration_seconds"),
        ),
        run_provenance_gate(
            source_asset_ids=kwargs.get("source_asset_ids"),
            rights_cleared=kwargs.get("rights_cleared"),
        ),
        run_factual_accuracy_gate(
            claims=kwargs.get("claims"),
            verified_ratio=kwargs.get("verified_ratio"),
        ),
        run_hallucination_gate(
            generated_text=kwargs.get("generated_text", ""),
            source_texts=kwargs.get("source_texts"),
        ),
        run_visual_relevance_gate(clip_score=kwargs.get("clip_score")),
    ]
    hard_fail = [r for r in results if not r.passed and r.mode != "deferred"]
    return {
        "passed": len(hard_fail) == 0,
        "gates": [
            {
                "gate_id": r.gate_id,
                "passed": r.passed,
                "score": r.score,
                "mode": r.mode,
                "message": r.message,
                "details": r.details,
            }
            for r in results
        ],
        "hard_fail_count": len(hard_fail),
    }
