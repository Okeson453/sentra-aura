"""Content routes for the Control Plane API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from control_plane_api.api.dependencies import get_db_session
from control_plane_api.schemas import (
    ContentPlanCreate, ContentPlanUpdate, ContentPlanResponse,
    ScriptCreate, ScriptUpdate, ScriptResponse,
    VideoCreate, VideoUpdate, VideoResponse,
    ClipCreate, ClipUpdate, ClipResponse,
    PaginationParams, PaginatedResponse,
)
from control_plane_api.services import ContentService

router = APIRouter()


# ------------------------------------------------------------------
# Content Plans
# ------------------------------------------------------------------

@router.get("/plans", response_model=PaginatedResponse)
async def list_plans(
    channel_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ContentService(db)
    return svc.list_plans(channel_id=channel_id, limit=pagination.limit, offset=pagination.offset)


@router.post("/plans", response_model=ContentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: ContentPlanCreate,
    db: Session = Depends(get_db_session),
) -> ContentPlanResponse:
    svc = ContentService(db)
    return svc.create_plan(data)


@router.patch("/plans/{plan_id}", response_model=ContentPlanResponse)
async def update_plan(
    plan_id: str,
    updates: ContentPlanUpdate,
    db: Session = Depends(get_db_session),
) -> ContentPlanResponse:
    svc = ContentService(db)
    plan = svc.update_plan(plan_id, updates)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content plan not found")
    return plan


# ------------------------------------------------------------------
# Scripts
# ------------------------------------------------------------------

@router.get("/scripts", response_model=PaginatedResponse)
async def list_scripts(
    content_plan_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ContentService(db)
    return svc.list_scripts(content_plan_id=content_plan_id, limit=pagination.limit, offset=pagination.offset)


@router.post("/scripts", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    data: ScriptCreate,
    db: Session = Depends(get_db_session),
) -> ScriptResponse:
    svc = ContentService(db)
    return svc.create_script(data)


@router.patch("/scripts/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    updates: ScriptUpdate,
    db: Session = Depends(get_db_session),
) -> ScriptResponse:
    svc = ContentService(db)
    script = svc.update_script(script_id, updates)
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


# ------------------------------------------------------------------
# Videos
# ------------------------------------------------------------------

@router.get("/videos", response_model=PaginatedResponse)
async def list_videos(
    channel_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ContentService(db)
    return svc.list_videos(channel_id=channel_id, limit=pagination.limit, offset=pagination.offset)


@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(
    data: VideoCreate,
    db: Session = Depends(get_db_session),
) -> VideoResponse:
    svc = ContentService(db)
    return svc.create_video(data)


@router.patch("/videos/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: str,
    updates: VideoUpdate,
    db: Session = Depends(get_db_session),
) -> VideoResponse:
    svc = ContentService(db)
    video = svc.update_video(video_id, updates)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


# ------------------------------------------------------------------
# Clips
# ------------------------------------------------------------------

@router.get("/clips", response_model=PaginatedResponse)
async def list_clips(
    video_id: str | None = None,
    channel_id: str | None = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse:
    svc = ContentService(db)
    return svc.list_clips(video_id=video_id, channel_id=channel_id, limit=pagination.limit, offset=pagination.offset)


@router.post("/clips", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    data: ClipCreate,
    db: Session = Depends(get_db_session),
) -> ClipResponse:
    svc = ContentService(db)
    return svc.create_clip(data)


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    updates: ClipUpdate,
    db: Session = Depends(get_db_session),
) -> ClipResponse:
    svc = ContentService(db)
    clip = svc.update_clip(clip_id, updates)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip
