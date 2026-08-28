"""FastAPI service for the Orchestrator."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware

from orchestrator.workflows import AgentWorkflow, LongFormVideoWorkflow
from orchestrator.activities import (
    execute_agent_task,
    research_topic,
    draft_script,
    produce_voice,
    generate_visuals,
    render_video,
)

app = FastAPI(title="SentraAura Orchestrator", version="0.1.0")
setup_middleware(app)
app.include_router(health_router, tags=["Health"])
