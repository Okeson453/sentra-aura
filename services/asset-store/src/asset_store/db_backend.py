"""Database backend for Asset Store metadata.

Provides SQLAlchemy-based metadata storage for assets and provenance records.
Replaces in-memory dict storage with PostgreSQL.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from asset_store.backend import StorageBackend
from asset_store.db.session import get_db


class DatabaseMetadataBackend:
    """Database backend for storing asset metadata and provenance.
    
    This backend handles the metadata storage (Asset and ProvenanceRecord)
    while delegating actual file storage to a StorageBackend (local, S3, etc.).
    """

    def __init__(self, storage_backend: StorageBackend | None = None) -> None:
        self.storage_backend = storage_backend or StorageBackend()

    async def upload(
        self,
        channel_id: str,
        tenant_id: str,
        asset_type: str,
        filename: str,
        data: bytes,
        content_type: str = "",
        metadata: dict[str, Any] | None = None,
        created_by: str = "",
        skip_scan: bool = False,
    ) -> Any:
        """Upload an asset with database metadata storage."""
        # Generate asset ID
        asset_id = str(uuid.uuid4())[:32]
        
        # Store the actual file data using the storage backend
        storage_path = f"{channel_id}/{asset_type}/{asset_id}/{filename}"
        result = await self.storage_backend.put(storage_path, data, content_type)
        
        # Calculate checksum
        checksum = hashlib.sha256(data).hexdigest()
        
        # Import here to avoid circular imports
        from asset_store.db.models import AssetORM, orm_to_dataclass_asset
        
        # Create and store the asset metadata in the database
        db = next(get_db())
        try:
            orm_asset = AssetORM(
                asset_id=asset_id,
                channel_id=channel_id,
                tenant_id=tenant_id,
                asset_type=asset_type,
                filename=filename,
                content_type=content_type or "application/octet-stream",
                size_bytes=len(data),
                storage_path=storage_path,
                storage_provider=result.get("provider", "local"),
                checksum=checksum,
                status="ACTIVE",
                metadata=metadata or {},
                created_by=created_by,
                updated_by=created_by,
            )
            db.add(orm_asset)
            db.commit()
            db.refresh(orm_asset)
            
            # Convert to dataclass for backwards compatibility
            return orm_to_dataclass_asset(orm_asset)
        finally:
            db.close()

    async def get(self, asset_id: str) -> Any:
        """Get an asset by ID from database."""
        from asset_store.db.models import AssetORM, orm_to_dataclass_asset
        
        db = next(get_db())
        try:
            orm_asset = db.query(AssetORM).filter(
                AssetORM.asset_id == asset_id,
                AssetORM.is_deleted == False
            ).first()
            if orm_asset:
                return orm_to_dataclass_asset(orm_asset)
            return None
        finally:
            db.close()

    async def download(self, asset_id: str) -> bytes:
        """Download asset data from storage backend."""
        asset = await self.get(asset_id)
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")
        return await self.storage_backend.get(asset.storage_path)

    async def delete(self, asset_id: str) -> bool:
        """Soft-delete an asset in database."""
        from asset_store.db.models import AssetORM
        
        db = next(get_db())
        try:
            orm_asset = db.query(AssetORM).filter(
                AssetORM.asset_id == asset_id,
                AssetORM.is_deleted == False
            ).first()
            if not orm_asset:
                return False
            
            orm_asset.is_deleted = True
            orm_asset.deleted_at = datetime.utcnow()
            db.commit()
            return True
        finally:
            db.close()

    async def add_provenance(
        self,
        asset_id: str,
        action: str,
        agent_id: str,
        source_asset_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Add a provenance record to database."""
        from asset_store.db.models import ProvenanceRecordORM, orm_to_dataclass_provenance
        
        db = next(get_db())
        try:
            orm_record = ProvenanceRecordORM(
                record_id=str(uuid.uuid4())[:32],
                asset_id=asset_id,
                action=action,
                agent_id=agent_id,
                source_asset_ids=source_asset_ids or [],
                metadata=metadata or {},
                tenant_id="",  # Will be populated by RLS context
                channel_id="",
                created_by=agent_id,
                updated_by=agent_id,
            )
            db.add(orm_record)
            db.commit()
            db.refresh(orm_record)
            
            return orm_to_dataclass_provenance(orm_record)
        finally:
            db.close()

    async def get_provenance(self, asset_id: str) -> list[Any]:
        """Get provenance records for an asset from database."""
        from asset_store.db.models import ProvenanceRecordORM, orm_to_dataclass_provenance
        
        db = next(get_db())
        try:
            orm_records = db.query(ProvenanceRecordORM).filter(
                ProvenanceRecordORM.asset_id == asset_id
            ).all()
            return [orm_to_dataclass_provenance(r) for r in orm_records]
        finally:
            db.close()

    async def list_assets(
        self,
        channel_id: str | None = None,
        asset_type: str | None = None,
    ) -> list[Any]:
        """List assets from database with optional filters."""
        from asset_store.db.models import AssetORM, orm_to_dataclass_asset
        
        db = next(get_db())
        try:
            query = db.query(AssetORM).filter(AssetORM.is_deleted == False)
            if channel_id:
                query = query.filter(AssetORM.channel_id == channel_id)
            if asset_type:
                query = query.filter(AssetORM.asset_type == asset_type)
            
            orm_assets = query.all()
            return [orm_to_dataclass_asset(a) for a in orm_assets]
        finally:
            db.close()

    async def scan_asset(self, asset_id: str) -> Any:
        """Rescan an asset for viruses."""
        from asset_store.virus_scanner import SignatureScanner
        asset = await self.get(asset_id)
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")
        data = await self.download(asset_id)
        scanner = SignatureScanner()
        return await scanner.scan(data, asset.filename)
