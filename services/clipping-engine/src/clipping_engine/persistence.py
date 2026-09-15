"""Shared SQLAlchemy persistence for the clipping API and queue worker."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from clipping_engine.config import ServiceConfig

Base = declarative_base()


class ClipJob(Base):
    __tablename__ = "clip_jobs"

    job_id = Column(String(36), primary_key=True)
    video_id = Column(String(255))
    channel_id = Column(String(255))
    tenant_id = Column(String(255), default="")
    status = Column(String(50), default="queued")
    progress_percent = Column(Integer, default=0)
    candidates = Column(JSON, default=list)
    segment_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    error_message = Column(Text)
    attempt_count = Column(Integer, nullable=False, default=0)
    claimed_at = Column(DateTime)


class Segment(Base):
    """Persisted manual or pipeline-derived segment (Architecture §6 / Backend §23)."""
    __tablename__ = "segments"

    segment_id = Column(String(64), primary_key=True)
    video_id = Column(String(255), nullable=False, index=True)
    channel_id = Column(String(255), default="")
    tenant_id = Column(String(255), default="")
    start_seconds = Column(Float, nullable=False, default=0.0)
    end_seconds = Column(Float, nullable=False, default=0.0)
    label = Column(String(255), default="")
    tags = Column(JSON, default=list)
    text = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RenderJob(Base):
    __tablename__ = "render_jobs"

    job_id = Column(String(36), primary_key=True)
    clip_id = Column(String(255))
    video_id = Column(String(255))
    status = Column(String(50), default="queued")
    progress_percent = Column(Integer, default=0)
    output_url = Column(Text, default="")
    output_format = Column(String(50), default="mp4")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    error_message = Column(Text)


def _ensure_worker_columns(engine: Engine) -> None:
    """Upgrade pre-worker schemas safely until deployments run the migration."""
    existing = {column["name"] for column in inspect(engine).get_columns("clip_jobs")}
    statements = []
    if "attempt_count" not in existing:
        statements.append("ALTER TABLE clip_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
    if "claimed_at" not in existing:
        statements.append("ALTER TABLE clip_jobs ADD COLUMN claimed_at TIMESTAMP NULL")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


config = ServiceConfig()
engine = create_engine(config.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
_ensure_worker_columns(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
