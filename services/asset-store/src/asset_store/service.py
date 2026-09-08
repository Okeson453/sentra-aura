"""Asset Store service layer.

Updated to use database-backed storage instead of in-memory dicts.
Fixes Findings F-023, F-024, F-025.
"""
from __future__ import annotations

import hashlib
from typing import Any

from asset_store.models import Asset, ProvenanceRecord
from asset_store.backend import StorageBackend, LocalStorageBackend
from asset_store.db_backend import DatabaseMetadataBackend
from asset_store.virus_scanner import VirusScanner, SignatureScanner, ScanResult


class AssetStoreService:
    """Service for managing assets with virus scanning and provenance.
    
    Uses database-backed storage for metadata instead of in-memory dicts.
    """

    def __init__(
        self,
        backend: StorageBackend | None = None,
        scanner: VirusScanner | None = None,
        metadata_backend: DatabaseMetadataBackend | None = None,
    ) -> None:
        self.backend = backend or LocalStorageBackend()
        self.scanner = scanner or SignatureScanner()
        self.metadata_backend = metadata_backend or DatabaseMetadataBackend(self.backend)

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
    ) -> Asset:
        """Upload an asset with optional virus scanning.
        
        Note: skip_scan parameter is now ignored for non-privileged users.
        Virus scanning is always performed unless explicitly disabled via config.
        """
        # Always perform virus scanning - skip_scan is ignored
        # This fixes Finding F-025 (skip_scan from request)
        scan_result = await self.scanner.scan(data, filename)
        if not scan_result.clean:
            raise ValueError(f"Virus scan failed: {scan_result.threat} ({scan_result.scanner})")

        # Use database backend for storage
        asset = await self.metadata_backend.upload(
            channel_id=channel_id,
            tenant_id=tenant_id,
            asset_type=asset_type,
            filename=filename,
            data=data,
            content_type=content_type or "application/octet-stream",
            metadata=metadata or {},
            created_by=created_by,
            skip_scan=False,  # Always scan
        )
        return asset

    async def get(self, asset_id: str) -> Asset | None:
        """Get an asset by ID."""
        return await self.metadata_backend.get(asset_id)

    async def download(self, asset_id: str) -> bytes:
        """Download asset data."""
        return await self.metadata_backend.download(asset_id)

    async def delete(self, asset_id: str) -> bool:
        """Delete an asset."""
        return await self.metadata_backend.delete(asset_id)

    async def add_provenance(
        self,
        asset_id: str,
        action: str,
        agent_id: str,
        source_asset_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenanceRecord:
        """Add a provenance record."""
        return await self.metadata_backend.add_provenance(
            asset_id=asset_id,
            action=action,
            agent_id=agent_id,
            source_asset_ids=source_asset_ids,
            metadata=metadata,
        )

    async def get_provenance(self, asset_id: str) -> list[ProvenanceRecord]:
        """Get provenance records for an asset."""
        return await self.metadata_backend.get_provenance(asset_id)

    async def list_assets(
        self,
        channel_id: str | None = None,
        asset_type: str | None = None,
    ) -> list[Asset]:
        """List assets with optional filters."""
        return await self.metadata_backend.list_assets(
            channel_id=channel_id,
            asset_type=asset_type,
        )

    async def scan_asset(self, asset_id: str) -> ScanResult:
        """Rescan an existing asset."""
        return await self.metadata_backend.scan_asset(asset_id)
