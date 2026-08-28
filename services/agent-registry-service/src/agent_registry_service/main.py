"""FastAPI application for the Agent Registry Service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from agent_registry_service.models import (
    AgentHealth,
    AgentRegistration,
    AgentStatus,
    AgentVersion,
    ErrorResponse,
    EvaluationRecord,
    EvaluationStatus,
    HealthResponse,
    HealthStatus,
    RegisteredAgent,
)
from agent_registry_service.store import AgentStore

logger = logging.getLogger(__name__)
store = AgentStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed the registry with the 12 canonical SentraAura domain agents."""
    canonical_agents = [
        ("executive_orchestrator_agent", "Executive Orchestrator", "intelligence",
         ["strategy", "planning", "orchestration", "portfolio_coordination"]),
        ("portfolio_strategy_agent", "Portfolio Strategy", "intelligence",
         ["portfolio_planning", "budget_allocation", "content_calendar", "risk_assessment"]),
        ("market_audience_intelligence_agent", "Market & Audience Intelligence", "intelligence",
         ["trend_analysis", "audience_segmentation", "competitor_analysis", "keyword_research"]),
        ("research_agent", "Research", "intelligence",
         ["web_search", "source_evaluation", "claim_extraction", "brief_synthesis"]),
        ("fact_verification_agent", "Fact Verification", "creative",
         ["claim_verification", "source_cross_reference", "confidence_scoring", "bias_detection"]),
        ("content_strategist_ideation_agent", "Content Strategist & Ideation", "creative",
         ["concept_generation", "thumbnail_ideation", "seo_optimization", "trend_alignment"]),
        ("scripting_agent", "Scripting", "creative",
         ["script_draft", "script_critique", "script_rewrite", "retention_optimization"]),
        ("voice_agent", "Voice", "creative",
         ["voiceover_planning", "tts_synthesis", "pacing_guidance", "emotion_mapping"]),
        ("visual_asset_agent", "Visual Asset", "creative",
         ["image_generation", "thumbnail_design", "b_roll_planning", "brand_consistency"]),
        ("scene_shot_agent", "Scene & Shot", "production",
         ["shot_planning", "scene_breakdown", "camera_direction", "lighting_notes"]),
        ("video_production_agent", "Video Production", "production",
         ["timeline_assembly", "audio_mixing", "color_grading", "export_optimization"]),
        ("localization_agent", "Localization", "production",
         ["translation", "dubbing", "subtitle_generation", "cultural_adaptation"]),
    ]
    for agent_id, name, domain, capabilities in canonical_agents:
        try:
            store.register(AgentRegistration(
                agent_id=agent_id,
                name=name,
                domain=domain,
                version="1.0.0",
                description=f"SentraAura {name} Agent",
                capabilities=capabilities,
                endpoint=f"agents/{agent_id}",
                status=AgentStatus.ACTIVE,
            ))
            # Seed a CANARY evaluation for each
            store.add_evaluation(EvaluationRecord(
                agent_id=agent_id,
                status=EvaluationStatus.CANARY,
                score=0.85,
                evaluator="system_bootstrap",
                notes=f"Initial CANARY evaluation for {agent_id} during service startup",
                metrics={"latency_ms": 120, "token_count": 450, "cost_usd": 0.03},
            ))
        except ValueError:
            pass  # Already registered
    logger.info("Agent Registry Service seeded with %d canonical agents", len(canonical_agents))
    yield
    logger.info("Agent Registry Service shutting down")


app = FastAPI(
    title="Agent Registry Service",
    version="1.0.0",
    description="Agent registration, versioning, capability discovery, health monitoring, and CANARY evaluation",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", checks={"store": {"status": "pass"}})


@app.get("/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    return HealthResponse(status="ready", checks={"store": {"status": "pass"}})


@app.get("/api/v1/agents", response_model=list[RegisteredAgent])
async def list_agents(
    domain: str | None = Query(None),
    status: AgentStatus | None = Query(None),
    capability: str | None = Query(None),
) -> list[RegisteredAgent]:
    return store.list_all(domain=domain, status=status, capability=capability)


@app.post("/api/v1/agents", response_model=RegisteredAgent, status_code=status.HTTP_201_CREATED)
async def register_agent(registration: AgentRegistration) -> RegisteredAgent:
    try:
        return store.register(registration)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.get("/api/v1/agents/{agent_id}", response_model=RegisteredAgent)
async def get_agent(agent_id: str) -> RegisteredAgent:
    agent = store.get(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    return agent


@app.put("/api/v1/agents/{agent_id}", response_model=RegisteredAgent)
async def update_agent(agent_id: str, registration: AgentRegistration) -> RegisteredAgent:
    try:
        return store.update(agent_id, registration)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.delete("/api/v1/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_agent(agent_id: str) -> Response:
    store.delete(agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/agents/{agent_id}/versions", response_model=list[AgentVersion])
async def list_versions(agent_id: str) -> list[AgentVersion]:
    if agent_id not in store._agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    return store.list_versions(agent_id)


@app.get("/api/v1/agents/{agent_id}/health", response_model=AgentHealth)
async def get_agent_health(agent_id: str) -> AgentHealth:
    health = store.get_health(agent_id)
    if not health:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    return health


@app.patch("/api/v1/agents/{agent_id}/health")
async def update_agent_health(agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if agent_id not in store._agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    health_status = HealthStatus(payload.get("health", "unknown"))
    store.update_health(agent_id, health_status)
    return {"agent_id": agent_id, "health": health_status.value, "updated_at": datetime.utcnow().isoformat()}


@app.post("/api/v1/agents/{agent_id}/evaluations", response_model=EvaluationRecord)
async def submit_evaluation(agent_id: str, record: EvaluationRecord) -> EvaluationRecord:
    if agent_id not in store._agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    record.agent_id = agent_id
    return store.add_evaluation(record)


@app.get("/api/v1/agents/{agent_id}/evaluations", response_model=list[EvaluationRecord])
async def get_evaluations(agent_id: str) -> list[EvaluationRecord]:
    if agent_id not in store._agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    return store.get_evaluations(agent_id)


@app.get("/api/v1/agents/{agent_id}/evaluations/canary")
async def get_canary_status(agent_id: str) -> dict[str, Any]:
    if agent_id not in store._agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")
    canary = store.get_canary_status(agent_id)
    if not canary:
        return {"agent_id": agent_id, "canary": None}
    return {"agent_id": agent_id, "canary": canary.model_dump()}


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error_code="VALIDATION_ERROR", message=str(exc)).model_dump(),
    )
