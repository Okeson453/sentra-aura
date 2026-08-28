"""Repository layer for the Control Plane API."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from control_plane_api.models import (
    Channel,
    ContentPlan,
    Script,
    Video,
    Clip,
    Publication,
    PerformanceRecord,
    Experiment,
    Policy,
    DecisionLog,
)


class ChannelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, channel_id: str) -> Channel | None:
        return self.db.query(Channel).filter(Channel.id == channel_id).first()

    def list(self, tenant_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Channel], int]:
        q = self.db.query(Channel)
        if tenant_id:
            q = q.filter(Channel.tenant_id == tenant_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Channel:
        channel = Channel(**data)
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def update(self, channel_id: str, updates: dict[str, Any]) -> Channel | None:
        channel = self.get(channel_id)
        if not channel:
            return None
        for k, v in updates.items():
            setattr(channel, k, v)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def delete(self, channel_id: str) -> bool:
        channel = self.get(channel_id)
        if not channel:
            return False
        self.db.delete(channel)
        self.db.commit()
        return True


class ContentPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, plan_id: str) -> ContentPlan | None:
        return self.db.query(ContentPlan).filter(ContentPlan.id == plan_id).first()

    def list(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[ContentPlan], int]:
        q = self.db.query(ContentPlan)
        if channel_id:
            q = q.filter(ContentPlan.channel_id == channel_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> ContentPlan:
        plan = ContentPlan(**data)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update(self, plan_id: str, updates: dict[str, Any]) -> ContentPlan | None:
        plan = self.get(plan_id)
        if not plan:
            return None
        for k, v in updates.items():
            setattr(plan, k, v)
        self.db.commit()
        self.db.refresh(plan)
        return plan


class ScriptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, script_id: str) -> Script | None:
        return self.db.query(Script).filter(Script.id == script_id).first()

    def list(self, content_plan_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Script], int]:
        q = self.db.query(Script)
        if content_plan_id:
            q = q.filter(Script.content_plan_id == content_plan_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Script:
        script = Script(**data)
        self.db.add(script)
        self.db.commit()
        self.db.refresh(script)
        return script


class VideoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, video_id: str) -> Video | None:
        return self.db.query(Video).filter(Video.id == video_id).first()

    def list(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Video], int]:
        q = self.db.query(Video)
        if channel_id:
            q = q.filter(Video.channel_id == channel_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Video:
        video = Video(**data)
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        return video


class ClipRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, clip_id: str) -> Clip | None:
        return self.db.query(Clip).filter(Clip.id == clip_id).first()

    def list(self, video_id: str | None = None, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Clip], int]:
        q = self.db.query(Clip)
        if video_id:
            q = q.filter(Clip.video_id == video_id)
        if channel_id:
            q = q.filter(Clip.channel_id == channel_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Clip:
        clip = Clip(**data)
        self.db.add(clip)
        self.db.commit()
        self.db.refresh(clip)
        return clip


class PublicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, publication_id: str) -> Publication | None:
        return self.db.query(Publication).filter(Publication.id == publication_id).first()

    def list(self, channel_id: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Publication], int]:
        q = self.db.query(Publication)
        if channel_id:
            q = q.filter(Publication.channel_id == channel_id)
        if status:
            q = q.filter(Publication.status == status)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Publication:
        pub = Publication(**data)
        self.db.add(pub)
        self.db.commit()
        self.db.refresh(pub)
        return pub


class PerformanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, record_id: str) -> PerformanceRecord | None:
        return self.db.query(PerformanceRecord).filter(PerformanceRecord.id == record_id).first()

    def get_by_publication(self, publication_id: str) -> PerformanceRecord | None:
        return self.db.query(PerformanceRecord).filter(PerformanceRecord.publication_id == publication_id).first()

    def create(self, data: dict[str, Any]) -> PerformanceRecord:
        rec = PerformanceRecord(**data)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec


class ExperimentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, experiment_id: str) -> Experiment | None:
        return self.db.query(Experiment).filter(Experiment.id == experiment_id).first()

    def list(self, channel_id: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Experiment], int]:
        q = self.db.query(Experiment)
        if channel_id:
            q = q.filter(Experiment.channel_id == channel_id)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Experiment:
        exp = Experiment(**data)
        self.db.add(exp)
        self.db.commit()
        self.db.refresh(exp)
        return exp


class PolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, policy_id: str) -> Policy | None:
        return self.db.query(Policy).filter(Policy.id == policy_id).first()

    def list(self, channel_id: str | None = None, policy_type: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[Policy], int]:
        q = self.db.query(Policy)
        if channel_id:
            q = q.filter(Policy.channel_id == channel_id)
        if policy_type:
            q = q.filter(Policy.policy_type == policy_type)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> Policy:
        policy = Policy(**data)
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy


class DecisionLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, decision_id: str) -> DecisionLog | None:
        return self.db.query(DecisionLog).filter(DecisionLog.id == decision_id).first()

    def list(self, channel_id: str | None = None, agent_type: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[DecisionLog], int]:
        q = self.db.query(DecisionLog)
        if channel_id:
            q = q.filter(DecisionLog.channel_id == channel_id)
        if agent_type:
            q = q.filter(DecisionLog.agent_type == agent_type)
        total = q.count()
        return q.offset(offset).limit(limit).all(), total

    def create(self, data: dict[str, Any]) -> DecisionLog:
        log = DecisionLog(**data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def override(self, decision_id: str, override_by: str, override_status: str) -> DecisionLog | None:
        log = self.get(decision_id)
        if not log:
            return None
        log.override_status = override_status
        log.override_by = override_by
        log.override_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(log)
        return log
