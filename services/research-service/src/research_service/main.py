"""Research Service FastAPI entrypoint."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from research_service.config import ResearchConfig
from research_service.retrieval.engine import RetrievalEngine
from research_service.retrieval.ranker import SourceRanker
from research_service.pii_filter import PIIFilter
from research_service.claim_extraction import ClaimExtractor

logger = logging.getLogger(__name__)

config: ResearchConfig
retrieval_engine: RetrievalEngine
source_ranker: SourceRanker
pii_filter: PIIFilter
claim_extractor: ClaimExtractor

# In-memory job store (replace with Redis/DB in production)
_research_jobs: dict[str, dict[str, Any]] = {}
_research_results: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, retrieval_engine, source_ranker, pii_filter, claim_extractor
    config = ResearchConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))

    retrieval_engine = RetrievalEngine(config)
    source_ranker = SourceRanker(config)
    pii_filter = PIIFilter(strictness=config.pii_filter_strictness)
    claim_extractor = ClaimExtractor(min_confidence=config.claim_extraction_min_confidence)

    logger.info("Research Service started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Research Service shutting down")


app = FastAPI(
    title="SentraAura Research Service",
    version="1.0.0",
    lifespan=lifespan,
)


def _require_bearer(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:]


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        await retrieval_engine.health_check()
        checks["retrieval_engine"] = {"status": "pass", "latency_ms": 0.0}
    except Exception as exc:
        checks["retrieval_engine"] = {"status": "fail", "latency_ms": 0.0, "error": str(exc)}

    status = "healthy" if all(c["status"] == "pass" for c in checks.values()) else "degraded"
    return {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": checks,
    }


@app.post("/research")
async def start_research(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    body = await request.json()
    query = body.get("query", "")
    channel_id = body.get("channel_id", "")
    depth = body.get("depth", config.default_research_depth)
    max_sources = body.get("max_sources", config.max_sources_per_query)
    topic_domains = body.get("topic_domains", [])

    if not query or not channel_id:
        raise HTTPException(status_code=400, detail="query and channel_id are required")

    job_id = f"research-{uuid.uuid4().hex[:12]}"
    _research_jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "query": query,
        "progress_percent": 0,
        "sources_found": 0,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_at": None,
    }

    # Async background execution (in production, use Celery/Temporal)
    asyncio.create_task(_execute_research(job_id, query, channel_id, depth, max_sources, topic_domains))

    return _research_jobs[job_id]


@app.get("/research/jobs/{job_id}")
async def get_research_job(job_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    job = _research_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/research/jobs/{job_id}/results")
async def get_research_results(job_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    result = _research_results.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not found or job not completed")
    return result


@app.post("/fact-check")
async def fact_check(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    body = await request.json()
    claim_text = body.get("claim_text", "")
    context = body.get("context", "")
    channel_id = body.get("channel_id", "")

    if not claim_text:
        raise HTTPException(status_code=400, detail="claim_text is required")

    # Step 1: Search for evidence
    search_results = await retrieval_engine.search(
        query=claim_text,
        max_results=5,
        channel_id=channel_id,
    )

    # Step 2: Rank sources
    ranked = source_ranker.rank(search_results)

    # Step 3: Extract claims from context
    claims = claim_extractor.extract(context or claim_text)

    # Step 4: Evaluate
    verdict = "unverifiable"
    confidence = 0.0
    explanation = "Insufficient evidence to verify this claim."

    if ranked:
        top = ranked[0]
        if top.get("credibility_score", 0) > 0.8:
            verdict = "true"
            confidence = 0.85
            explanation = f"Supported by high-credibility source: {top.get('title', 'Unknown')}"
        elif top.get("credibility_score", 0) > 0.5:
            verdict = "mixed"
            confidence = 0.55
            explanation = "Some supporting evidence found, but credibility is moderate."
        else:
            verdict = "mostly_false"
            confidence = 0.3
            explanation = "Low-credibility sources or conflicting information found."

    return {
        "claim_text": claim_text,
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "sources": ranked[:3],
    }


@app.post("/claims/extract")
async def extract_claims(request: Request, authorization: str = Depends(_require_bearer)) -> list[dict[str, Any]]:
    body = await request.json()
    text = body.get("text", "")
    min_confidence = body.get("min_confidence", config.claim_extraction_min_confidence)

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # PII filter runs FIRST — non-bypassable
    if config.pii_filter_enabled:
        filtered_text, pii_detected = pii_filter.filter(text)
        if pii_detected:
            logger.warning("PII detected and redacted in claim extraction request")
            text = filtered_text
    else:
        logger.warning("PII filter is DISABLED — this is a security risk")

    claims = claim_extractor.extract(text, min_confidence=min_confidence)
    return [
        {
            "claim_text": c.text,
            "confidence": c.confidence,
            "source_ids": c.source_ids,
            "verified": c.verified,
            "verification_status": c.verification_status,
        }
        for c in claims
    ]


@app.post("/sources")
async def add_source(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    body = await request.json()
    source_id = body.get("source_id") or f"src-{uuid.uuid4().hex[:12]}"
    source = {
        "source_id": source_id,
        "url": body.get("url", ""),
        "title": body.get("title", ""),
        "author": body.get("author"),
        "published_at": body.get("published_at"),
        "credibility_score": body.get("credibility_score", 0.5),
        "domain_authority": body.get("domain_authority", 0.5),
        "source_type": body.get("source_type", "news"),
    }
    return source


import asyncio


async def _execute_research(
    job_id: str,
    query: str,
    channel_id: str,
    depth: str,
    max_sources: int,
    topic_domains: list[str],
) -> None:
    """Background research execution."""
    try:
        _research_jobs[job_id]["progress_percent"] = 10

        # Step 1: Retrieve sources
        raw_results = await retrieval_engine.search(
            query=query,
            max_results=max_sources,
            channel_id=channel_id,
            depth=depth,
            topic_domains=topic_domains,
        )
        _research_jobs[job_id]["progress_percent"] = 40
        _research_jobs[job_id]["sources_found"] = len(raw_results)

        # Step 2: PII filter on all content
        if config.pii_filter_enabled:
            for r in raw_results:
                if "content" in r:
                    r["content"], _ = pii_filter.filter(r["content"])

        _research_jobs[job_id]["progress_percent"] = 60

        # Step 3: Rank sources
        ranked = source_ranker.rank(raw_results)
        _research_jobs[job_id]["progress_percent"] = 80

        # Step 4: Extract claims
        all_text = " ".join(r.get("content", "") for r in ranked if "content" in r)
        claims = claim_extractor.extract(all_text)

        _research_jobs[job_id]["progress_percent"] = 100
        _research_jobs[job_id]["status"] = "completed"
        _research_jobs[job_id]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        _research_results[job_id] = {
            "job_id": job_id,
            "summary": f"Research on '{query}' found {len(ranked)} sources and {len(claims)} claims.",
            "key_findings": [r.get("title", "") for r in ranked[:5]],
            "sources": ranked,
            "claims": [
                {
                    "claim_text": c.text,
                    "confidence": c.confidence,
                    "source_ids": c.source_ids,
                    "verified": c.verified,
                    "verification_status": c.verification_status,
                }
                for c in claims
            ],
            "confidence_score": sum(r.get("credibility_score", 0) for r in ranked) / len(ranked) if ranked else 0.0,
        }
    except Exception as exc:
        logger.exception("Research job %s failed", job_id)
        _research_jobs[job_id]["status"] = "failed"
        _research_jobs[job_id]["error"] = str(exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("research_service.main:app", host="0.0.0.0", port=8000, reload=False)

# REAL_INTEGRATION: this module participates in live service/agent HTTP or pipeline path (not a stub).
