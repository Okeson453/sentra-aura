"""SQLAlchemy models for the Control Plane API."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.pool import NullPool

from control_plane_api.db.base import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(32), primary_key=True)
    tenant_id = Column(String(32), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    platform_channel_id = Column(String(255))
    status = Column(String(20), default="ACTIVE")
    niche = Column(String(255))
    target_audience = Column(Text)
    content_mix = Column(JSON, default=dict)
    schedule = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    updated_by = Column(String(255))

    content_plans = relationship("ContentPlan", back_populates="channel", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="channel", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="channel", cascade="all, delete-orphan")


class ContentPlan(Base):
    __tablename__ = "content_plans"

    id = Column(String(32), primary_key=True)
    channel_id = Column(String(32), ForeignKey("channels.id"), nullable=False, index=True)
    topic = Column(String(500), nullable=False)
    status = Column(String(20), default="DRAFT")
    strategy = Column(JSON, default=dict)
    budget = Column(JSON, default=dict)
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel = relationship("Channel", back_populates="content_plans")
    scripts = relationship("Script", back_populates="content_plan", cascade="all, delete-orphan")


class Script(Base):
    __tablename__ = "scripts"

    id = Column(String(32), primary_key=True)
    content_plan_id = Column(String(32), ForeignKey("content_plans.id"), nullable=False, index=True)
    title = Column(String(500))
    content = Column(Text)
    status = Column(String(20), default="DRAFT")
    word_count = Column(Integer, default=0)
    estimated_duration = Column(Integer, default=0)
    disclosure_tags = Column(JSON, default=list)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    content_plan = relationship("ContentPlan", back_populates="scripts")
    videos = relationship("Video", back_populates="script", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id = Column(String(32), primary_key=True)
    script_id = Column(String(32), ForeignKey("scripts.id"), nullable=False, index=True)
    channel_id = Column(String(32), ForeignKey("channels.id"), nullable=False, index=True)
    status = Column(String(20), default="RENDERING")
    duration_seconds = Column(Integer, default=0)
    resolution = Column(String(20), default="1920x1080")
    asset_manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    script = relationship("Script", back_populates="videos")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String(32), primary_key=True)
    video_id = Column(String(32), ForeignKey("videos.id"), nullable=False, index=True)
    channel_id = Column(String(32), ForeignKey("channels.id"), nullable=False, index=True)
    clip_type = Column(String(50), default="HIGHLIGHT")
    status = Column(String(20), default="READY_TO_PUBLISH")
    start_ms = Column(Integer, default=0)
    end_ms = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    aspect_ratio = Column(String(10), default="9:16")
    scores = Column(JSON, default=dict)
    lineage = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    video = relationship("Video", back_populates="clips")
    publications = relationship("Publication", back_populates="clip", cascade="all, delete-orphan")


class Publication(Base):
    __tablename__ = "publications"

    id = Column(String(32), primary_key=True)
    channel_id = Column(String(32), ForeignKey("channels.id"), nullable=False, index=True)
    video_id = Column(String(32), ForeignKey("videos.id"))
    clip_id = Column(String(32), ForeignKey("clips.id"))
    platform = Column(String(50), nullable=False)
    platform_id = Column(String(255))
    platform_url = Column(Text)
    status = Column(String(20), default="SCHEDULED")
    scheduled_at = Column(DateTime)
    published_at = Column(DateTime)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel = relationship("Channel", back_populates="publications")
    clip = relationship("Clip", back_populates="publications")
    performance = relationship("PerformanceRecord", back_populates="publication", uselist=False, cascade="all, delete-orphan")


class PerformanceRecord(Base):
    __tablename__ = "performance_records"

    id = Column(String(32), primary_key=True)
    publication_id = Column(String(32), ForeignKey("publications.id"), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)
    views = Column(Integer, default=0)
    watch_time_seconds = Column(Integer, default=0)
    retention_curve = Column(JSON, default=list)
    ctr = Column(Float, default=0.0)
    engagement_rate = Column(Float, default=0.0)
    subscriber_gain = Column(Integer, default=0)
    traffic_sources = Column(JSON, default=dict)
    measured_at = Column(DateTime, default=datetime.utcnow)

    publication = relationship("Publication", back_populates="performance")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String(32), primary_key=True)
    channel_id = Column(String(32), ForeignKey("channels.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hypothesis = Column(Text)
    variant_ids = Column(JSON, default=list)
    control_id = Column(String(32))
    asset_id = Column(String(32))
    metrics = Column(JSON, default=list)
    status = Column(String(20), default="DRAFT")
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    required_sample_size = Column(Integer, default=1000)
    results = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel = relationship("Channel", back_populates="experiments")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String(32), primary_key=True)
    channel_id = Column(String(32), nullable=False, index=True)
    policy_type = Column(String(50), nullable=False)
    autonomy_level = Column(String(10), default="L1")
    rules = Column(JSON, default=dict)
    weights = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id = Column(String(32), primary_key=True)
    channel_id = Column(String(32), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    decision = Column(Text, nullable=False)
    reasoning = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    alternatives_rejected = Column(JSON, default=list)
    human_override_possible = Column(Boolean, default=True)
    override_status = Column(String(20), default="PENDING")
    override_by = Column(String(255))
    override_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_engine(database_url: str):
    return create_engine(database_url, poolclass=NullPool, echo=False)


def get_sessionmaker(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
