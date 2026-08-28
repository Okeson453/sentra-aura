"""Publishing routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import (
    PublicationCreate, PublicationUpdate, PublicationResponse,
    PerformanceCreate, PerformanceResponse,
    PaginationParams, PaginatedResponse,
)
from control_plane_api.services import PublishingService

router = APIRouter()


@router.get("/publications", response_model=PaginatedResponse)
async def list_publications(
    channel_id: str | None = None,
    status: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = PublishingService(db)
    return svc.list_publications(channel_id=channel_id, status=status, limit=pagination.limit, offset=pagination.offset)


@router.post("/publications", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
async def create_publication(
    data: PublicationCreate,
    db: Session = Depends(get_db_session),
) -> PublicationResponse:
    svc = PublishingService(db)
    return svc.create_publication(data)


@router.patch("/publications/{publication_id}", response_model=PublicationResponse)
async def update_publication(
    publication_id: str,
    updates: PublicationUpdate,
    db: Session = Depends(get_db_session),
) -> PublicationResponse:
    svc = PublishingService(db)
    pub = svc.update_publication(publication_id, updates)
    if not pub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    return pub


@router.get("/publications/{publication_id}/performance", response_model=PerformanceResponse)
async def get_performance(
    publication_id: str,
    db: Session = Depends(get_db_session),
) -> PerformanceResponse:
    svc = PublishingService(db)
    perf = svc.get_performance(publication_id)
    if not perf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance record not found")
    return perf


@router.post("/performance", response_model=PerformanceResponse, status_code=status.HTTP_201_CREATED)
async def create_performance(
    data: PerformanceCreate,
    db: Session = Depends(get_db_session),
) -> PerformanceResponse:
    svc = PublishingService(db)
    return svc.create_performance(data)
