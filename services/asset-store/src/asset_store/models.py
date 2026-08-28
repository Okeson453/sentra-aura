"""Models for the Asset Store."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class Asset:
    """A content asset in the store."""
    asset_id: str = field(default_factory=lambda: str(uuid4())[:32])
    channel_id: str = ""
    tenant_id: str = ""
    asset_type: str = ""
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    storage_path: str = ""
    storage_provider: str = "local"
    checksum: str = ""
    status: str = "ACTIVE"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    updated_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "asset_type": self.asset_type,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "storage_provider": self.storage_provider,
            "checksum": self.checksum,
            "status": self.status,
            "provenance": self.provenance,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ProvenanceRecord:
    """Provenance record for an asset."""
    record_id: str = field(default_factory=lambda: str(uuid4())[:32])
    asset_id: str = ""
    action: str = ""
    agent_id: str = ""
    source_asset_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
