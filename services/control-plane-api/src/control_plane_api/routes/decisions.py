"""Decision log routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import (
    DecisionLogCreate, DecisionLogOverride, DecisionLogResponse,
    PaginationParams, PaginatedResponse,
)
from control_plane_api.services import DecisionService

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_decisions(
    channel_id: str | None = None,
    agent_type: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = DecisionService(db)
    return svc.list(channel_id=channel_id, agent_type=agent_type, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=DecisionLogResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    data: DecisionLogCreate,
    db: Session = Depends(get_db_session),
) -> DecisionLogResponse:
    svc = DecisionService(db)
    return svc.create(data)


@router.post("/{decision_id}/override", response_model=DecisionLogResponse)
async def override_decision(
    decision_id: str,
    override: DecisionLogOverride,
    override_by: str,
    db: Session = Depends(get_db_session),
) -> DecisionLogResponse:
    svc = DecisionService(db)
    try:
        log = svc.override(decision_id, override_by, override)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return log
