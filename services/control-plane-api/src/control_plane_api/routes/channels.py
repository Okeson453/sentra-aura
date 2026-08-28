"""Channel routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session, get_current_tenant, rate_limit
from control_plane_api.schemas import (
    ChannelCreate, ChannelUpdate, ChannelResponse,
    PaginationParams, PaginatedResponse, ErrorResponse,
)
from control_plane_api.services import ChannelService

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_channels(
    tenant_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ChannelService(db)
    return svc.list(tenant_id=tenant_id, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: ChannelCreate,
    request: Request,
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    try:
        return svc.create(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    ch = svc.get(channel_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ch


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    updates: ChannelUpdate,
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    ch = svc.update(channel_id, updates)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ch


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db_session),
) -> None:
    svc = ChannelService(db)
    ok = svc.delete(channel_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
