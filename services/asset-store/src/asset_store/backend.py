"""Storage backend for the Asset Store."""
from __future__ import annotations

import hashlib
import os
from typing import Any

from asset_store.models import Asset


class StorageBackend:
    """Abstract storage backend."""

    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
        raise NotImplementedError

    async def get(self, path: str) -> bytes:
        raise NotImplementedError

    async def delete(self, path: str) -> bool:
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        raise NotImplementedError

    async def presigned_url(self, path: str, expiry_seconds: int = 3600) -> str:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str = "/tmp/sentra-aura-assets") -> None:
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
        full_path = os.path.join(self.base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)
        return {
            "path": path,
            "size": len(data),
            "checksum": hashlib.sha256(data).hexdigest(),
        }

    async def get(self, path: str) -> bytes:
        full_path = os.path.join(self.base_path, path)
        with open(full_path, "rb") as f:
            return f.read()

    async def delete(self, path: str) -> bool:
        full_path = os.path.join(self.base_path, path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, path: str) -> bool:
        return os.path.exists(os.path.join(self.base_path, path))

    async def presigned_url(self, path: str, expiry_seconds: int = 3600) -> str:
        return f"file://{os.path.join(self.base_path, path)}"
