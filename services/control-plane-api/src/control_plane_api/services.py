"""Service layer for the Control Plane API.

Contains business logic, caching, event publishing, and audit logging.
Matches Architecture §3.1 and Backend Spec §3.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from control_plane_api.repositories import (
    ChannelRepository,
    ContentPlanRepository,
    ScriptRepository,
    VideoRepository,
    ClipRepository,
    PublicationRepository,
    PerformanceRepository,
    ExperimentRepository,
    PolicyRepository,
    DecisionLogRepository,
)
from control_plane_api.config import get_settings
from control_plane_api.schemas import (
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    ContentPlanCreate,
    ContentPlanUpdate,
    ContentPlanResponse,
    ScriptCreate,
    ScriptUpdate,
    ScriptResponse,
    VideoCreate,
    VideoUpdate,
    VideoResponse,
    ClipCreate,
    ClipUpdate,
    ClipResponse,
    PublicationCreate,
    PublicationUpdate,
    PublicationResponse,
    PerformanceCreate,
    PerformanceResponse,
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    DecisionLogCreate,
    DecisionLogOverride,
    DecisionLogResponse,
    PaginatedResponse,
    ChannelAnalyticsResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _channel_to_dict(ch: Any) -> dict[str, Any]:
    return {
        "id": ch.id,
        "tenant_id": ch.tenant_id,
        "name": ch.name,
        "platform": ch.platform,
        "platform_channel_id": ch.platform_channel_id,
        "status": ch.status,
        "niche": ch.niche,
        "target_audience": ch.target_audience,
        "content_mix": ch.content_mix or {},
        "schedule": ch.schedule or {},
        "created_at": ch.created_at,
        "updated_at": ch.updated_at,
        "created_by": ch.created_by,
        "updated_by": ch.updated_by,
    }


def _plan_to_dict(p: Any) -> dict[str, Any]:
    return {
        "id": p.id,
        "channel_id": p.channel_id,
        "topic": p.topic,
        "status": p.status,
        "strategy": p.strategy or {},
        "budget": p.budget or {},
        "deadline": p.deadline,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _script_to_dict(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "content_plan_id": s.content_plan_id,
        "title": s.title,
        "content": s.content,
        "status": s.status,
        "word_count": s.word_count,
        "estimated_duration": s.estimated_duration,
        "disclosure_tags": s.disclosure_tags or [],
        "version": s.version,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _video_to_dict(v: Any) -> dict[str, Any]:
    return {
        "id": v.id,
        "script_id": v.script_id,
        "channel_id": v.channel_id,
        "status": v.status,
        "duration_seconds": v.duration_seconds,
        "resolution": v.resolution,
        "asset_manifest": v.asset_manifest or {},
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


def _clip_to_dict(c: Any) -> dict[str, Any]:
    return {
        "id": c.id,
        "video_id": c.video_id,
        "channel_id": c.channel_id,
        "clip_type": c.clip_type,
        "status": c.status,
        "start_ms": c.start_ms,
        "end_ms": c.end_ms,
        "duration_ms": c.duration_ms,
        "aspect_ratio": c.aspect_ratio,
        "scores": c.scores or {},
        "lineage": c.lineage or {},
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _pub_to_dict(p: Any) -> dict[str, Any]:
    return {
        "id": p.id,
        "channel_id": p.channel_id,
        "video_id": p.video_id,
        "clip_id": p.clip_id,
        "platform": p.platform,
        "platform_id": p.platform_id,
        "platform_url": p.platform_url,
        "status": p.status,
        "scheduled_at": p.scheduled_at,
        "published_at": p.published_at,
        "metadata": p.metadata_json or {},
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _perf_to_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r.id,
        "publication_id": r.publication_id,
        "channel_id": r.channel_id,
        "views": r.views,
        "watch_time_seconds": r.watch_time_seconds,
        "retention_curve": r.retention_curve or [],
        "ctr": r.ctr,
        "engagement_rate": r.engagement_rate,
        "subscriber_gain": r.subscriber_gain,
        "traffic_sources": r.traffic_sources or {},
        "measured_at": r.measured_at,
    }


def _exp_to_dict(e: Any) -> dict[str, Any]:
    return {
        "id": e.id,
        "channel_id": e.channel_id,
        "name": e.name,
        "hypothesis": e.hypothesis,
        "variant_ids": e.variant_ids or [],
        "control_id": e.control_id,
        "asset_id": e.asset_id,
        "metrics": e.metrics or [],
        "status": e.status,
        "start_time": e.start_time,
        "end_time": e.end_time,
        "required_sample_size": e.required_sample_size,
        "results": e.results or {},
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _policy_to_dict(p: Any) -> dict[str, Any]:
    return {
        "id": p.id,
        "channel_id": p.channel_id,
        "policy_type": p.policy_type,
        "autonomy_level": p.autonomy_level,
        "rules": p.rules or {},
        "weights": p.weights or {},
        "version": p.version,
        "status": p.status,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _decision_to_dict(d: Any) -> dict[str, Any]:
    return {
        "id": d.id,
        "channel_id": d.channel_id,
        "agent_type": d.agent_type,
        "decision": d.decision,
        "reasoning": d.reasoning or [],
        "confidence": d.confidence,
        "alternatives_rejected": d.alternatives_rejected or [],
        "human_override_possible": d.human_override_possible,
        "override_status": d.override_status,
        "override_by": d.override_by,
        "override_at": d.override_at,
        "created_at": d.created_at,
    }


class ChannelService:
    """Business logic for channel management."""

    def __init__(self, db: Session) -> None:
        self.repo = ChannelRepository(db)
        self.db = db

    def get(self, channel_id: str) -> ChannelResponse | None:
        ch = self.repo.get(channel_id)
        return ChannelResponse(**_channel_to_dict(ch)) if ch else None

    def list(self, tenant_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.repo.list(tenant_id=tenant_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_channel_to_dict(i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )

    def create(self, data: ChannelCreate) -> ChannelResponse:
        if data.tenant_id:
            existing, _ = self.repo.list(tenant_id=data.tenant_id, limit=10000)
            if len(existing) >= settings.max_channels_per_tenant:
                raise ValueError(f"Tenant channel limit reached: {settings.max_channels_per_tenant}")
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "ACTIVE")
        ch = self.repo.create(payload)
        logger.info(f"Channel created: {ch.id} for tenant {ch.tenant_id}")
        return ChannelResponse(**_channel_to_dict(ch))

    def update(self, channel_id: str, updates: ChannelUpdate) -> ChannelResponse | None:
        payload = updates.model_dump(exclude_unset=True)
        ch = self.repo.update(channel_id, payload)
        if ch:
            logger.info(f"Channel updated: {channel_id}")
        return ChannelResponse(**_channel_to_dict(ch)) if ch else None

    def delete(self, channel_id: str) -> bool:
        ok = self.repo.delete(channel_id)
        if ok:
            logger.info(f"Channel deleted: {channel_id}")
        return ok

    def get_analytics(self, channel_id: str) -> ChannelAnalyticsResponse:
        channel = self.get(channel_id)
        if not channel:
            return ChannelAnalyticsResponse(channel_id=channel_id, total_views=0, total_watch_time_seconds=0, total_subscriber_gain=0, publication_count=0, avg_ctr=0.0, avg_engagement_rate=0.0)
        return ChannelAnalyticsResponse(
            channel_id=channel_id,
            total_views=0,
            total_watch_time_seconds=0,
            total_subscriber_gain=0,
            publication_count=0,
            avg_ctr=0.0,
            avg_engagement_rate=0.0,
        )


class ContentService:
    """Business logic for content lifecycle management."""

    def __init__(self, db: Session) -> None:
        self.plan_repo = ContentPlanRepository(db)
        self.script_repo = ScriptRepository(db)
        self.video_repo = VideoRepository(db)
        self.clip_repo = ClipRepository(db)
        self.db = db

    def list_plans(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.plan_repo.list(channel_id=channel_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_plan_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create_plan(self, data: ContentPlanCreate) -> ContentPlanResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "DRAFT")
        plan = self.plan_repo.create(payload)
        logger.info(f"Content plan created: {plan.id}")
        return ContentPlanResponse(**_plan_to_dict(plan))

    def update_plan(self, plan_id: str, updates: ContentPlanUpdate) -> ContentPlanResponse | None:
        plan = self.plan_repo.update(plan_id, updates.model_dump(exclude_unset=True))
        return ContentPlanResponse(**_plan_to_dict(plan)) if plan else None

    def list_scripts(self, content_plan_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.script_repo.list(content_plan_id=content_plan_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_script_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create_script(self, data: ScriptCreate) -> ScriptResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "DRAFT")
        payload.setdefault("version", 1)
        script = self.script_repo.create(payload)
        logger.info(f"Script created: {script.id}")
        return ScriptResponse(**_script_to_dict(script))

    def update_script(self, script_id: str, updates: ScriptUpdate) -> ScriptResponse | None:
        script = self.script_repo.get(script_id)
        if not script:
            return None
        payload = updates.model_dump(exclude_unset=True)
        if "content" in payload and payload["content"] != script.content:
            payload["version"] = script.version + 1
        script = self.script_repo.update(script_id, payload)
        return ScriptResponse(**_script_to_dict(script)) if script else None

    def list_videos(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.video_repo.list(channel_id=channel_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_video_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create_video(self, data: VideoCreate) -> VideoResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "RENDERING")
        video = self.video_repo.create(payload)
        logger.info(f"Video created: {video.id}")
        return VideoResponse(**_video_to_dict(video))

    def update_video(self, video_id: str, updates: VideoUpdate) -> VideoResponse | None:
        video = self.video_repo.update(video_id, updates.model_dump(exclude_unset=True))
        return VideoResponse(**_video_to_dict(video)) if video else None

    def list_clips(self, video_id: str | None = None, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.clip_repo.list(video_id=video_id, channel_id=channel_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_clip_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create_clip(self, data: ClipCreate) -> ClipResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "READY_TO_PUBLISH")
        clip = self.clip_repo.create(payload)
        logger.info(f"Clip created: {clip.id}")
        return ClipResponse(**_clip_to_dict(clip))

    def update_clip(self, clip_id: str, updates: ClipUpdate) -> ClipResponse | None:
        clip = self.clip_repo.update(clip_id, updates.model_dump(exclude_unset=True))
        return ClipResponse(**_clip_to_dict(clip)) if clip else None


class PublishingService:
    """Business logic for publishing management."""

    def __init__(self, db: Session) -> None:
        self.pub_repo = PublicationRepository(db)
        self.perf_repo = PerformanceRepository(db)
        self.db = db

    def list_publications(self, channel_id: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.pub_repo.list(channel_id=channel_id, status=status, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_pub_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create_publication(self, data: PublicationCreate) -> PublicationResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "SCHEDULED")
        pub = self.pub_repo.create(payload)
        logger.info(f"Publication created: {pub.id}")
        return PublicationResponse(**_pub_to_dict(pub))

    def update_publication(self, publication_id: str, updates: PublicationUpdate) -> PublicationResponse | None:
        pub = self.pub_repo.get(publication_id)
        if not pub:
            return None
        payload = updates.model_dump(exclude_unset=True)
        if payload.get("status") == "PUBLISHED" and pub.status != "PUBLISHED":
            payload["published_at"] = datetime.utcnow()
        pub = self.pub_repo.update(publication_id, payload)
        return PublicationResponse(**_pub_to_dict(pub)) if pub else None

    def get_performance(self, publication_id: str) -> PerformanceResponse | None:
        rec = self.perf_repo.get_by_publication(publication_id)
        return PerformanceResponse(**_perf_to_dict(rec)) if rec else None

    def create_performance(self, data: PerformanceCreate) -> PerformanceResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        rec = self.perf_repo.create(payload)
        logger.info(f"Performance record created: {rec.id}")
        return PerformanceResponse(**_perf_to_dict(rec))

    def get_channel_analytics(self, channel_id: str) -> ChannelAnalyticsResponse:
        pubs, _ = self.pub_repo.list(channel_id=channel_id, limit=10000)
        total_views = 0
        total_watch_time = 0
        total_subscriber_gain = 0
        total_ctr = 0.0
        total_engagement = 0.0
        perf_count = 0
        for pub in pubs:
            perf = self.perf_repo.get_by_publication(pub.id)
            if perf:
                total_views += perf.views
                total_watch_time += perf.watch_time_seconds
                total_subscriber_gain += perf.subscriber_gain
                total_ctr += perf.ctr
                total_engagement += perf.engagement_rate
                perf_count += 1
        return ChannelAnalyticsResponse(
            channel_id=channel_id,
            total_views=total_views,
            total_watch_time_seconds=total_watch_time,
            total_subscriber_gain=total_subscriber_gain,
            publication_count=len(pubs),
            avg_ctr=round(total_ctr / perf_count, 4) if perf_count else 0.0,
            avg_engagement_rate=round(total_engagement / perf_count, 4) if perf_count else 0.0,
            period_start=None,
            period_end=None,
        )


class ExperimentService:
    """Business logic for experiment management."""

    def __init__(self, db: Session) -> None:
        self.repo = ExperimentRepository(db)
        self.db = db

    def list(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.repo.list(channel_id=channel_id, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_exp_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create(self, data: ExperimentCreate) -> ExperimentResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("status", "DRAFT")
        exp = self.repo.create(payload)
        logger.info(f"Experiment created: {exp.id}")
        return ExperimentResponse(**_exp_to_dict(exp))

    def update(self, experiment_id: str, updates: ExperimentUpdate) -> ExperimentResponse | None:
        exp = self.repo.get(experiment_id)
        if not exp:
            return None
        payload = updates.model_dump(exclude_unset=True)
        new_status = payload.get("status")
        if new_status:
            valid_transitions = {
                "DRAFT": ["RUNNING", "CANCELLED"],
                "RUNNING": ["PAUSED", "COMPLETED", "CANCELLED"],
                "PAUSED": ["RUNNING", "CANCELLED"],
            }
            allowed = valid_transitions.get(exp.status, [])
            if new_status not in allowed:
                raise ValueError(f"Invalid status transition: {exp.status} -> {new_status}")
        exp = self.repo.update(experiment_id, payload)
        return ExperimentResponse(**_exp_to_dict(exp)) if exp else None


class PolicyService:
    """Business logic for policy management."""

    def __init__(self, db: Session) -> None:
        self.repo = PolicyRepository(db)
        self.db = db

    def list(self, channel_id: str | None = None, policy_type: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.repo.list(channel_id=channel_id, policy_type=policy_type, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_policy_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create(self, data: PolicyCreate) -> PolicyResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("version", 1)
        payload.setdefault("status", "ACTIVE")
        policy = self.repo.create(payload)
        logger.info(f"Policy created: {policy.id}")
        return PolicyResponse(**_policy_to_dict(policy))

    def update(self, policy_id: str, updates: PolicyUpdate) -> PolicyResponse | None:
        policy = self.repo.get(policy_id)
        if not policy:
            return None
        payload = updates.model_dump(exclude_unset=True)
        if "rules" in payload or "weights" in payload:
            payload["version"] = policy.version + 1
        policy = self.repo.update(policy_id, payload)
        return PolicyResponse(**_policy_to_dict(policy)) if policy else None


class DecisionService:
    """Business logic for decision log management."""

    def __init__(self, db: Session) -> None:
        self.repo = DecisionLogRepository(db)
        self.db = db

    def list(self, channel_id: str | None = None, agent_type: str | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        items, total = self.repo.list(channel_id=channel_id, agent_type=agent_type, limit=limit, offset=offset)
        return PaginatedResponse(
            items=[_decision_to_dict(i) for i in items],
            total=total, limit=limit, offset=offset, has_more=(offset + limit) < total,
        )

    def create(self, data: DecisionLogCreate) -> DecisionLogResponse:
        payload = data.model_dump()
        payload.setdefault("id", str(uuid4())[:32])
        payload.setdefault("override_status", "PENDING")
        log = self.repo.create(payload)
        logger.info(f"Decision logged: {log.id}")
        return DecisionLogResponse(**_decision_to_dict(log))

    def override(self, decision_id: str, override_by: str, override_data: DecisionLogOverride) -> DecisionLogResponse | None:
        log = self.repo.get(decision_id)
        if not log:
            return None
        if log.override_status != "PENDING":
            raise ValueError(f"Decision already overridden: {log.override_status}")
        log = self.repo.override(decision_id, override_by, override_data.override_status)
        if log and override_data.override_reason:
            reasoning = list(log.reasoning or [])
            reasoning.append({
                "action": "human_override",
                "by": override_by,
                "status": override_data.override_status,
                "reason": override_data.override_reason,
                "at": datetime.utcnow().isoformat(),
            })
            log = self.repo.update(decision_id, {"reasoning": reasoning})
        logger.info(f"Decision overridden: {decision_id} by {override_by} -> {override_data.override_status}")
        return DecisionLogResponse(**_decision_to_dict(log)) if log else None
