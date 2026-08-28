"""Policy routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import (
    PolicyCreate, PolicyUpdate, PolicyResponse,
    PaginationParams, PaginatedResponse,
)
from control_plane_api.services import PolicyService

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_policies(
    channel_id: str | None = None,
    policy_type: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = PolicyService(db)
    return svc.list(channel_id=channel_id, policy_type=policy_type, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    data: PolicyCreate,
    db: Session = Depends(get_db_session),
) -> PolicyResponse:
    svc = PolicyService(db)
    return svc.create(data)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    updates: PolicyUpdate,
    db: Session = Depends(get_db_session),
) -> PolicyResponse:
    svc = PolicyService(db)
    policy = svc.update(policy_id, updates)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return policy
