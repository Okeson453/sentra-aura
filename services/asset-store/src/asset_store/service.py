"""Asset Store service layer."""
from __future__ import annotations

import hashlib
from typing import Any

from asset_store.models import Asset, ProvenanceRecord
from asset_store.backend import StorageBackend, LocalStorageBackend
from asset_store.virus_scanner import VirusScanner, SignatureScanner, ScanResult


class AssetStoreService:
    """Service for managing assets with virus scanning and provenance."""

    def __init__(self, backend: StorageBackend | None = None, scanner: VirusScanner | None = None) -> None:
        self.backend = backend or LocalStorageBackend()
        self.scanner = scanner or SignatureScanner()
        self._assets: dict[str, Asset] = {}
        self._provenance: dict[str, list[ProvenanceRecord]] = {}

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
        """Upload an asset with optional virus scanning."""
        if not skip_scan:
            scan_result = await self.scanner.scan(data, filename)
            if not scan_result.clean:
                raise ValueError(f"Virus scan failed: {scan_result.threat} ({scan_result.scanner})")

        asset = Asset(
            channel_id=channel_id,
            tenant_id=tenant_id,
            asset_type=asset_type,
            filename=filename,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            metadata=metadata or {},
            created_by=created_by,
        )
        storage_path = f"{channel_id}/{asset_type}/{asset.asset_id}/{filename}"
        result = await self.backend.put(storage_path, data, content_type)
        asset.storage_path = storage_path
        asset.storage_provider = result.get("provider", "local")
        self._assets[asset.asset_id] = asset
        return asset

    async def get(self, asset_id: str) -> Asset | None:
        """Get an asset by ID."""
        return self._assets.get(asset_id)

    async def download(self, asset_id: str) -> bytes:
        """Download asset data."""
        asset = self._assets.get(asset_id)
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")
        return await self.backend.get(asset.storage_path)

    async def delete(self, asset_id: str) -> bool:
        """Delete an asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False
        await self.backend.delete(asset.storage_path)
        asset.status = "DELETED"
        return True

    async def add_provenance(self, asset_id: str, action: str, agent_id: str, source_asset_ids: list[str] | None = None, metadata: dict[str, Any] | None = None) -> ProvenanceRecord:
        """Add a provenance record."""
        record = ProvenanceRecord(
            asset_id=asset_id,
            action=action,
            agent_id=agent_id,
            source_asset_ids=source_asset_ids or [],
            metadata=metadata or {},
        )
        if asset_id not in self._provenance:
            self._provenance[asset_id] = []
        self._provenance[asset_id].append(record)
        return record

    async def get_provenance(self, asset_id: str) -> list[ProvenanceRecord]:
        """Get provenance records for an asset."""
        return self._provenance.get(asset_id, [])

    async def list_assets(self, channel_id: str | None = None, asset_type: str | None = None) -> list[Asset]:
        """List assets."""
        assets = list(self._assets.values())
        if channel_id:
            assets = [a for a in assets if a.channel_id == channel_id]
        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        return [a for a in assets if a.status == "ACTIVE"]

    async def scan_asset(self, asset_id: str) -> ScanResult:
        """Rescan an existing asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")
        data = await self.backend.get(asset.storage_path)
        return await self.scanner.scan(data, asset.filename)
