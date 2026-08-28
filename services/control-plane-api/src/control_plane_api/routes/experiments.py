"""Experiment routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import (
    ExperimentCreate, ExperimentUpdate, ExperimentResponse,
    PaginationParams, PaginatedResponse,
)
from control_plane_api.services import ExperimentService

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_experiments(
    channel_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ExperimentService(db)
    return svc.list(channel_id=channel_id, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    data: ExperimentCreate,
    db: Session = Depends(get_db_session),
) -> ExperimentResponse:
    svc = ExperimentService(db)
    return svc.create(data)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    updates: ExperimentUpdate,
    db: Session = Depends(get_db_session),
) -> ExperimentResponse:
    svc = ExperimentService(db)
    try:
        exp = svc.update(experiment_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return exp
