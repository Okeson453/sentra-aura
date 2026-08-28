"""Mock Provider Gateway for SentraAura local development.

Simulates AI provider APIs (OpenAI, Anthropic, ElevenLabs, Runway, etc.)
for local testing without real API keys or costs.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SentraAura Mock Provider Gateway")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class CompletionRequest(BaseModel):
    prompt: str
    model: str | None = "mock-gpt-4"
    temperature: float | None = 0.7
    max_tokens: int | None = 500


class EmbeddingRequest(BaseModel):
    text: str
    model: str | None = "mock-embedding-3"


class TTSRequest(BaseModel):
    text: str
    voice: str | None = "mock-voice-1"


class ImageGenRequest(BaseModel):
    prompt: str
    size: str | None = "1024x1024"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "mock-provider-gateway"}


@app.post("/v1/complete")
async def complete(req: CompletionRequest) -> dict[str, Any]:
    latency_ms = random.randint(50, 150)
    time.sleep(latency_ms / 1000)
    prompt_hash = hashlib.md5(req.prompt.encode()).hexdigest()[:8]
    lower = req.prompt.lower()

    if "rewrite" in lower and (
        "critique feedback" in lower or "original script" in lower or "rewrite guidelines" in lower
    ):
        text = json.dumps({
            "rewritten_script": {
                "hook": f"[REWRITE-{prompt_hash}] Pattern-interrupt hook.",
                "intro": "Credibility opener.",
                "sections": [{"title": "Body", "content": f"Revised body ({prompt_hash}).", "estimated_duration": 180, "b_roll_notes": "diagrams"}],
                "cta": "Subscribe.",
                "outro": "Thanks for watching.",
            },
            "word_count": 120,
            "confidence_score": 0.82,
        })
    elif "critique" in lower and (
        "script to critique" in lower or "critique dimensions" in lower or "you are the script critique" in lower
    ):
        text = json.dumps({
            "overall_score": 0.55,
            "strengths": ["Clear structure"],
            "weaknesses": ["Hook is weak"],
            "action_items": ["Strengthen hook"],
            "approval_status": "approved_with_revisions",
        })
    elif "draft" in lower or "script structure requirements" in lower or "youtube video script" in lower:
        text = json.dumps({
            "script": {
                "hook": f"[DRAFT-{prompt_hash}] Opening.",
                "intro": "Intro.",
                "sections": [{"title": "Point One", "content": f"Draft body ({prompt_hash}).", "estimated_duration": 120, "b_roll_notes": "montage"}],
                "cta": "Subscribe.",
                "outro": "Bye.",
            },
            "word_count": 90,
        })
    elif "fact verification" in lower or "service-level fact-check" in lower or ("verifications" in lower and "claim" in lower):
        text = json.dumps({"verifications": [], "overall_confidence": 0.7, "unverifiable_count": 0, "recommendations": [], "contradiction_alerts": []})
    elif (
        "content strategist" in lower
        or "ideation" in lower
        or "video concepts" in lower
        or "hook candidates" in lower
        or "num concepts" in lower
    ):
        topic = "topic"
        for line in req.prompt.splitlines():
            if line.lower().startswith("topic:"):
                topic = line.split(":", 1)[-1].strip() or topic
                break
        text = json.dumps({
            "concepts": [
                {
                    "title": f"{topic}: Deep Dive ({prompt_hash})",
                    "hook": f"Most people misunderstand {topic}.",
                    "angle": "myth-busting",
                    "format": "long-form",
                    "thumbnail_concept": f"Bold title about {topic}",
                    "target_keywords": [topic.lower(), "explained"],
                    "estimated_ctr": "9.2%",
                    "production_complexity": "medium",
                    "uniqueness_score": 0.78,
                    "trend_alignment": "high",
                },
                {
                    "title": f"5 {topic} Mistakes to Avoid",
                    "hook": f"Avoid these {topic} pitfalls.",
                    "angle": "listicle",
                    "format": "long-form",
                    "thumbnail_concept": "Numbered warnings",
                    "target_keywords": [topic.lower(), "mistakes"],
                    "estimated_ctr": "10.1%",
                    "production_complexity": "low",
                    "uniqueness_score": 0.55,
                    "trend_alignment": "medium",
                },
            ],
            "recommended_concept": {
                "title": f"{topic}: Deep Dive ({prompt_hash})",
                "hook": f"Most people misunderstand {topic}.",
                "target_keywords": [topic.lower(), "explained"],
                "uniqueness_score": 0.78,
                "trend_alignment": "high",
            },
            "content_strategy": {
                "summary": f"Strategy focused on {topic} authority content.",
                "pillars": [topic, "fundamentals"],
                "series_opportunities": [f"{topic} series"],
            },
            "topic_portfolio": [{"topic": topic, "priority": 1, "pillar": "core", "planned_formats": ["long-form"]}],
            "idea_set": [f"{topic} deep dive", f"{topic} mistakes"],
            "hook_candidates": [f"Most people misunderstand {topic}.", f"Avoid these {topic} pitfalls."],
            "content_series_potential": True,
            "seo_optimization_notes": [f"Primary keyword: {topic.lower()}"],
        })

    elif "research agent" in lower or "retrieved evidence" in lower or "untrusted_data" in lower or ("research brief" in lower and "content strategist" not in lower):
        topic = "topic"
        for line in req.prompt.splitlines():
            if line.lower().startswith("topic:"):
                topic = line.split(":", 1)[-1].strip() or topic
                break
        text = json.dumps({
            "executive_summary": f"Provider research brief on '{topic}' (hash {prompt_hash}).",
            "key_findings": [{"finding": f"{topic} is actively studied", "confidence": "high", "source_count": 2}],
            "confidence_score": 0.78,
            "claims": [{"claim_text": f"{topic} matters", "confidence": 0.7, "source_ids": [], "verified": False}],
        })
    elif "portfolio strategy" in lower or "portfolio_plan_summary" in lower or "channel_allocations" in lower or "allocate resources" in lower:
        portfolio = "portfolio"
        for line in req.prompt.splitlines():
            if "portfolio:" in line.lower():
                portfolio = line.split(":", 1)[-1].strip() or portfolio
                break
        text = json.dumps({
            "portfolio_plan_summary": f"Provider plan for {portfolio} (hash {prompt_hash}).",
            "channel_allocations": [{"channel_id": "ch_primary", "budget_usd": 600, "video_count": 4, "priority": 1, "topic_quota": {"core": 2}}],
            "topic_quotas": {"core": 3},
            "budget_allocation": {"ch_primary": 600, "production": 0.35},
            "cross_channel_themes": [portfolio, "growth"],
            "content_calendar": [],
            "risk_assessment": [],
            "success_metrics": {},
        })
    elif "executive orchestrator" in lower or "strategy_summary" in lower or "publishing_schedule" in lower:
        channel = "channel"
        for line in req.prompt.splitlines():
            if "channel:" in line.lower():
                channel = line.split(":", 1)[-1].strip() or channel
                break
        text = json.dumps({
            "strategy_summary": f"Provider strategy for {channel} (hash {prompt_hash}).",
            "content_pillars": [f"P-{prompt_hash[:4]}-A", f"P-{prompt_hash[:4]}-B", f"P-{prompt_hash[:4]}-C"],
            "publishing_schedule": [{"week": 1, "videos": [f"{channel} opener"]}],
            "resource_allocation": {"research": 0.22, "scripting": 0.28, "production": 0.35, "distribution": 0.15},
            "risk_mitigation": ["Buffer"],
            "kpis": {"target_ctr": 0.07},
        })
    elif "market & audience" in lower or "market intelligence" in lower or "opportunity_score" in lower or "competitor_gaps" in lower or "trend_signals" in lower:
        segment = "general"
        import re as _re
        for line in req.prompt.splitlines():
            low = line.lower()
            if "niche:" in low or "channel_niche" in low or "market_segment" in low:
                segment = line.split(":", 1)[-1].strip().strip('"').strip("'") or segment
                break
        m = _re.search(r'"topic"\s*:\s*"([^"]+)"', req.prompt)
        if m:
            segment = m.group(1)
        text = json.dumps({
            "market_summary": f"Provider analysis for segment '{segment}' (hash {prompt_hash}).",
            "top_trends": [
                {"topic": segment, "velocity": 0.88, "saturation": 0.25, "opportunity_score": 88, "confidence": "high", "volume": 90000},
                {"topic": f"{segment} tools", "velocity": 0.7, "saturation": 0.4, "opportunity_score": 70, "confidence": "medium", "volume": 30000},
            ],
            "audience_segments": [{"name": f"{segment} enthusiasts", "interest": segment}],
            "competitor_gaps": [f"Few competitors deep-dive {segment}"],
            "keyword_opportunities": [f"{segment} tutorial"],
            "content_recommendations": [f"Series on {segment}"],
            "confidence_assessment": {"trend_data": "high", "audience_data": "medium", "competitor_data": "medium"},
        })

    elif "voice" in lower and ("voiceover" in lower or "synthesize" in lower or "tts" in lower or "pacing" in lower or "emotion" in lower):
        text = json.dumps({
            "segments": [
                {"id": "hook", "emotion": "engaging", "emphasis_words": ["you"], "pause_instructions": ["short pause after hook"]},
                {"id": "intro", "emotion": "confident", "emphasis_words": [], "pause_instructions": []},
            ],
            "voice_profile_recommendation": {"voice_id": "mock-voice-1", "style": "neutral", "language": "en"},
            "pacing_notes": f"Conversational pacing (hash {prompt_hash}).",
            "consistency_checklist": ["Match energy across segments"],
        })

    elif "agent tool" in lower:
        # Generic agent tool responses — echo topic for variance
        topic = "topic"
        for line in req.prompt.splitlines():
            if "topic" in line.lower() and (":" in line or '"' in line):
                if "marine" in line.lower():
                    topic = "marine snow ecology"
                elif "orbital" in line.lower():
                    topic = "orbital debris mitigation"
                break
        if "marine" in lower:
            topic = "marine snow ecology"
        if "orbital" in lower:
            topic = "orbital debris mitigation"
        text = json.dumps({
            "status": "ok",
            "topic": topic,
            "artifacts": [{"type": "result", "topic": topic, "hash": prompt_hash}],
            "summary": f"Processed {topic} ({prompt_hash})",
        })

    else:
        text = f"Mock completion for prompt hash {prompt_hash}. This is a simulated response for local development."

    return {
        "text": text,
        "provider": "mock",
        "model": req.model,
        "usage": {
            "prompt_tokens": len(req.prompt.split()),
            "completion_tokens": max(20, len(text.split())),
            "total_tokens": len(req.prompt.split()) + max(20, len(text.split())),
            "estimated_cost_usd": round(0.001 * (len(req.prompt.split()) / 100), 6),
        },
        "latency_ms": latency_ms,
    }


@app.post("/v1/embed")
async def embed(req: EmbeddingRequest) -> dict[str, Any]:
    """Mock text embedding."""
    embedding = [round(random.uniform(-1, 1), 6) for _ in range(1536)]
    return {
        "embedding": embedding,
        "provider": "mock",
        "model": req.model,
        "usage": {
            "prompt_tokens": len(req.text.split()),
            "estimated_cost_usd": 0.0001,
        },
    }


@app.post("/v1/tts")
async def tts(req: TTSRequest) -> dict[str, Any]:
    """Mock text-to-speech with word-level timings."""
    words = req.text.split()
    t = 0.0
    timings = []
    for w in words:
        dur = max(0.12, len(w) / 14.0)
        timings.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur
    duration = round(t, 3) if timings else max(1.0, len(req.text) / 15.0)
    return {
        "audio_url": f"http://localhost:8081/fixtures/tts_responses/mock_{hashlib.md5(req.text.encode()).hexdigest()[:8]}.mp3",
        "provider": "mock",
        "voice": req.voice,
        "duration_seconds": duration,
        "word_timings": timings,
        "format": "mp3",
    }


@app.post("/v1/images/generate")
async def image_generate(req: ImageGenRequest) -> dict[str, Any]:
    """Mock image generation."""
    return {
        "image_url": "http://localhost:8081/fixtures/image_responses/mock_image.png",
        "provider": "mock",
        "resolution": req.size,
    }


@app.get("/v1/providers/health")
async def provider_health() -> dict[str, str]:
    """Return mock provider health status."""
    return {
        "mock": "healthy",
        "openai": "healthy",
        "anthropic": "healthy",
        "elevenlabs": "healthy",
        "runway": "healthy",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)
