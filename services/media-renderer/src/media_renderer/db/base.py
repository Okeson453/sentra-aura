"""SQLAlchemy declarative base for Media Renderer.

Shared base, mixins, and utilities for database models.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, BigInteger, DateTime, Boolean, JSON, Integer, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def generate_short_id() -> str:
    """Generate a short URL-safe UUID."""
    import base64
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")[:12]


class AuditMixin:
    """Mixin adding created_at, updated_at, created_by, updated_by columns."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)


class TenantMixin:
    """Mixin adding tenant_id and channel_id for multi-tenancy."""

    tenant_id = Column(String(32), nullable=False, index=True)
    channel_id = Column(String(32), nullable=False, index=True)


class SoftDeleteMixin:
    """Mixin adding soft-delete support."""

    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(255), nullable=True)
