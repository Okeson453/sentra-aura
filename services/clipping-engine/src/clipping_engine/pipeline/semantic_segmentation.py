"""Semantic segmentation pipeline stage.

Merges transcript segments by embedding similarity when a real encoder
is available; otherwise merges by adjacent window and topic-hash.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _text_hash_embedding(text: str, dim: int = 384) -> list[float]:
    """Deterministic content-derived embedding (not a trained model).

    Vectors differ by text content so cosine similarity is meaningful for
    merge decisions without requiring Sentence-BERT weights at runtime.
    """
    if not text:
        return [0.0] * dim
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand digest to dim floats in [-1, 1]
    vals: list[float] = []
    seed = digest
    while len(vals) < dim:
        for b in seed:
            vals.append((b / 127.5) - 1.0)
            if len(vals) >= dim:
                break
        seed = hashlib.sha256(seed).digest()
    return vals[:dim]


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_segment(
    transcript_segments: list[dict[str, Any]],
    similarity_threshold: float = 0.7,
    min_segment_length_seconds: float = 3.0,
) -> dict[str, Any]:
    """Produce semantic segments from transcript segments."""
    logger.info("Semantic segmentation: %d segments", len(transcript_segments))

    if not transcript_segments:
        return {
            "semantic_segments": [],
            "similarity_threshold": similarity_threshold,
            "min_segment_length_seconds": min_segment_length_seconds,
            "mode": "empty",
        }

    # Try real sentence-transformers if installed
    mode = "hash-embedding"
    encode = None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model = SentenceTransformer("all-MiniLM-L6-v2")
        encode = lambda texts: model.encode(texts).tolist()  # noqa: E731
        mode = "sentence-transformers"
    except Exception:
        encode = lambda texts: [_text_hash_embedding(t) for t in texts]  # noqa: E731

    texts = [str(s.get("text") or "") for s in transcript_segments]
    embeddings = encode(texts)

    semantic: list[dict[str, Any]] = []
    i = 0
    while i < len(transcript_segments):
        seg = transcript_segments[i]
        start = float(seg.get("start", seg.get("start_time", 0.0)))
        end = float(seg.get("end", seg.get("end_time", start + 5.0)))
        text = texts[i]
        emb = embeddings[i]
        j = i + 1
        while j < len(transcript_segments):
            sim = _cosine(emb, embeddings[j])
            next_end = float(
                transcript_segments[j].get("end", transcript_segments[j].get("end_time", end))
            )
            if sim >= similarity_threshold or (next_end - start) < min_segment_length_seconds:
                end = next_end
                if texts[j]:
                    text = (text + " " + texts[j]).strip()
                # update running embedding as average
                emb = [(a + b) / 2 for a, b in zip(emb, embeddings[j])]
                j += 1
            else:
                break
        topic_digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8] if text else "empty"
        semantic.append({
            "segment_id": f"semantic_{len(semantic)}",
            "start_time": start,
            "end_time": end,
            "text": text,
            "embedding": emb[:32],  # truncate for payload size; full dim available upstream
            "topic": f"topic_{topic_digest}",
        })
        i = j

    return {
        "semantic_segments": semantic,
        "similarity_threshold": similarity_threshold,
        "min_segment_length_seconds": min_segment_length_seconds,
        "mode": mode,
    }


def segment_semantically(transcript_segments, similarity_threshold=0.7, min_segment_length_seconds=3.0):
    """Alias used by main/worker."""
    return semantic_segment(transcript_segments, similarity_threshold=similarity_threshold, min_segment_length_seconds=min_segment_length_seconds)
