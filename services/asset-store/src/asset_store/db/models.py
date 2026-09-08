"""SQLAlchemy ORM models for Asset Store.

Matches Architecture §4.1 and Backend Spec §4.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, String, BigInteger, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship

from asset_store.db.base import Base, AuditMixin, TenantMixin, SoftDeleteMixin


class AssetORM(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """SQLAlchemy ORM model for a content asset.
    
    Replaces the dataclass Asset with a proper database model.
    """
    __tablename__ = "assets"

    asset_id = Column(String(32), primary_key=True, index=True)
    asset_type = Column(String(64), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String(1024), nullable=False)
    storage_provider = Column(String(64), nullable=False, default="local")
    checksum = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    metadata = Column(JSON, nullable=False, default={})

    # Provenance records for this asset
    provenance_records = relationship("ProvenanceRecordORM", back_populates="asset", cascade="all, delete-orphan")


class ProvenanceRecordORM(Base, AuditMixin, TenantMixin):
    """SQLAlchemy ORM model for provenance records.
    
    Replaces the dataclass ProvenanceRecord with a proper database model.
    """
    __tablename__ = "provenance_records"

    record_id = Column(String(32), primary_key=True, index=True)
    asset_id = Column(String(32), index=True)
    action = Column(String(64), nullable=False)
    agent_id = Column(String(64), nullable=False)
    source_asset_ids = Column(JSON, nullable=False, default=[])
    metadata = Column(JSON, nullable=False, default={})

    # Relationship to asset
    asset = relationship("AssetORM", back_populates="provenance_records")


# Conversion functions for backwards compatibility
def orm_to_dataclass_asset(orm: AssetORM) -> dict[str, Any]:
    """Convert AssetORM to dict format matching Asset dataclass."""
    return {
        "asset_id": orm.asset_id,
        "channel_id": orm.channel_id,
        "tenant_id": orm.tenant_id,
        "asset_type": orm.asset_type,
        "filename": orm.filename,
        "content_type": orm.content_type,
        "size_bytes": orm.size_bytes,
        "storage_path": orm.storage_path,
        "storage_provider": orm.storage_provider,
        "checksum": orm.checksum,
        "status": orm.status,
        "provenance": {},
        "metadata": orm.metadata or {},
        "created_at": orm.created_at,
        "updated_at": orm.updated_at,
        "created_by": orm.created_by or "",
        "updated_by": orm.updated_by or "",
    }


def orm_to_dataclass_provenance(orm: ProvenanceRecordORM) -> dict[str, Any]:
    """Convert ProvenanceRecordORM to dict format matching ProvenanceRecord dataclass."""
    return {
        "record_id": orm.record_id,
        "asset_id": orm.asset_id,
        "action": orm.action,
        "agent_id": orm.agent_id,
        "source_asset_ids": orm.source_asset_ids or [],
        "metadata": orm.metadata or {},
        "created_at": orm.created_at,
    }
