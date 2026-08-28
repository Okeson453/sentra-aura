"""Analytics routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import ChannelAnalyticsResponse
from control_plane_api.services import PublishingService

router = APIRouter()


@router.get("/channels/{channel_id}", response_model=ChannelAnalyticsResponse)
async def get_channel_analytics(
    channel_id: str,
    db: Session = Depends(get_db_session),
) -> ChannelAnalyticsResponse:
    svc = PublishingService(db)
    return svc.get_channel_analytics(channel_id)
