"""Quality gates for clipping / media pipeline (Architecture §9)."""
from clipping_engine.quality.gates import (
    GateResult,
    run_audio_quality_gate,
    run_factual_accuracy_gate,
    run_hallucination_gate,
    run_provenance_gate,
    run_visual_relevance_gate,
    run_all_gates,
)

__all__ = [
    "GateResult",
    "run_audio_quality_gate",
    "run_factual_accuracy_gate",
    "run_hallucination_gate",
    "run_provenance_gate",
    "run_visual_relevance_gate",
    "run_all_gates",
]
