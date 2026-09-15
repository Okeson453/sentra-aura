"""Sentence transformer model wrapper.

Loads sentence-transformers when installed; otherwise provides deterministic
content-hash embeddings so similarity and clustering remain functional.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    if not text:
        return [0.0] * dim
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vals: list[float] = []
    seed = digest
    while len(vals) < dim:
        for b in seed:
            vals.append((b / 127.5) - 1.0)
            if len(vals) >= dim:
                break
        seed = hashlib.sha256(seed).digest()
    return vals[:dim]


class SentenceTransformerModel:
    """Wrapper for sentence embedding models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: Any = None
        self._backend = "hash"
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(model_name)
            self._backend = "sentence-transformers"
            logger.info("SentenceTransformerModel loaded: %s", model_name)
        except Exception as exc:
            logger.info(
                "SentenceTransformerModel using hash backend (%s unavailable: %s)",
                model_name,
                exc,
            )

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts to embedding vectors."""
        logger.info("Encoding %d texts (backend=%s)", len(texts), self._backend)
        if self._model is not None:
            try:
                return self._model.encode(texts).tolist()
            except Exception as exc:
                logger.warning("Model encode failed, falling back to hash: %s", exc)
        return [_hash_embed(t) for t in texts]

    def similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def backend(self) -> str:
        return self._backend
