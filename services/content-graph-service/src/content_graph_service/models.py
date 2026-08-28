"""SQLAlchemy models for the Content Asset Graph."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, create_engine
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.pool import NullPool

from content_graph_service.db.base import Base


class ContentNode(Base):
    __tablename__ = "content_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type = Column(String(50), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)
    tenant_id = Column(String(32), nullable=False, index=True)
    title = Column(String(500))
    description = Column(Text)
    status = Column(String(20), default="ACTIVE")
    version = Column(Integer, default=1)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    updated_by = Column(String(255))

    outgoing_edges = relationship("ContentEdge", foreign_keys="ContentEdge.source_id", back_populates="source")
    incoming_edges = relationship("ContentEdge", foreign_keys="ContentEdge.target_id", back_populates="target")
    lineage_records = relationship("LineageRecord", back_populates="node", cascade="all, delete-orphan")


class ContentEdge(Base):
    __tablename__ = "content_edges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(36), ForeignKey("content_nodes.id"), nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("content_nodes.id"), nullable=False, index=True)
    edge_type = Column(String(50), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)
    tenant_id = Column(String(32), nullable=False, index=True)
    weight = Column(Float, default=1.0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("ContentNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target = relationship("ContentNode", foreign_keys=[target_id], back_populates="incoming_edges")


class LineageRecord(Base):
    __tablename__ = "lineage_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String(36), ForeignKey("content_nodes.id"), nullable=False, index=True)
    tenant_id = Column(String(32), nullable=False, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    agent_id = Column(String(255))
    action = Column(String(255))
    inputs = Column(JSON, default=dict)
    outputs = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    node = relationship("ContentNode", back_populates="lineage_records")


def get_engine(database_url: str):
    return create_engine(database_url, poolclass=NullPool, echo=False)


def get_sessionmaker(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
