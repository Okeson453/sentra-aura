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
    pagination: PaginationParams = Depends(),
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    """List channels for the authenticated tenant only.

    The tenant scope is taken from authenticated context; a caller can no
    longer omit the filter (which previously returned every tenant's rows)
    or name someone else's tenant.
    """
    svc = ChannelService(db)
    return svc.list(tenant_id=tenant_id, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: ChannelCreate,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    # A body that asserts a different tenant is a mismatch, not a directive.
    if data.tenant_id and data.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch: the request targets a tenant the caller is not authorised to act on",
        )
    try:
        return svc.create(data, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    ch = svc.get(channel_id, tenant_id=tenant_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ch


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    updates: ChannelUpdate,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db_session),
) -> ChannelResponse:
    svc = ChannelService(db)
    ch = svc.update(channel_id, updates, tenant_id=tenant_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ch


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db_session),
) -> None:
    svc = ChannelService(db)
    ok = svc.delete(channel_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
