"""SQLAlchemy ORM models for Asset Store.

Matches Architecture §4.1 and Backend Spec §4.
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from asset_store.db.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin
from asset_store.models import Asset, ProvenanceRecord


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
    # ``metadata`` is reserved by the SQLAlchemy Declarative API. The Python
    # attribute is renamed; the physical column keeps its name so no migration
    # is required.
    asset_metadata = Column("metadata", JSON, nullable=False, default={})

    # Provenance records for this asset
    provenance_records = relationship("ProvenanceRecordORM", back_populates="asset", cascade="all, delete-orphan")


class ProvenanceRecordORM(Base, AuditMixin, TenantMixin):
    """SQLAlchemy ORM model for provenance records.
    
    Replaces the dataclass ProvenanceRecord with a proper database model.
    """
    __tablename__ = "provenance_records"

    record_id = Column(String(32), primary_key=True, index=True)
    # FK is required: relationship() cannot resolve the join without it, and
    # mapper configuration failed repo-wide as a result.
    asset_id = Column(String(32), ForeignKey("assets.asset_id"), index=True)
    action = Column(String(64), nullable=False)
    agent_id = Column(String(64), nullable=False)
    source_asset_ids = Column(JSON, nullable=False, default=[])
    # ``metadata`` is reserved by the SQLAlchemy Declarative API. The Python
    # attribute is renamed; the physical column keeps its name so no migration
    # is required.
    asset_metadata = Column("metadata", JSON, nullable=False, default={})

    # Relationship to asset
    asset = relationship("AssetORM", back_populates="provenance_records")


# Conversion functions for backwards compatibility
def orm_to_dataclass_asset(orm: AssetORM) -> Asset:
    """Convert an AssetORM row to the Asset dataclass.

    Despite its name and docstring this previously returned a plain ``dict``.
    ``AssetStoreService`` declares ``-> Asset`` and the routes read attributes,
    so every caller failed with
    ``AttributeError: 'dict' object has no attribute 'asset_id'``.
    """
    return Asset(
        asset_id=orm.asset_id,
        channel_id=orm.channel_id,
        tenant_id=orm.tenant_id,
        asset_type=orm.asset_type,
        filename=orm.filename,
        content_type=orm.content_type,
        size_bytes=orm.size_bytes,
        storage_path=orm.storage_path,
        storage_provider=orm.storage_provider,
        checksum=orm.checksum,
        status=orm.status,
        provenance={},
        metadata=orm.asset_metadata or {},
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        created_by=orm.created_by or "",
        updated_by=orm.updated_by or "",
    )


def orm_to_dataclass_provenance(orm: ProvenanceRecordORM) -> ProvenanceRecord:
    """Convert a ProvenanceRecordORM row to the ProvenanceRecord dataclass."""
    return ProvenanceRecord(
        record_id=orm.record_id,
        asset_id=orm.asset_id,
        action=orm.action,
        agent_id=orm.agent_id,
        source_asset_ids=orm.source_asset_ids or [],
        metadata=orm.asset_metadata or {},
        created_at=orm.created_at,
    )
