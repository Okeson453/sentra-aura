"""Google Cloud Storage backend for SentraAura Asset Store."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from asset_store.backend import StorageBackend

logger = logging.getLogger(__name__)


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(
        self,
        bucket: str,
        project_id: str | None = None,
        credentials_path: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.project_id = project_id
        self.credentials_path = credentials_path
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage
                if self.credentials_path:
                    self._client = storage.Client.from_service_account_json(self.credentials_path, project=self.project_id)
                else:
                    self._client = storage.Client(project=self.project_id)
            except ImportError:
                raise RuntimeError("google-cloud-storage is required for GCS backend")
        return self._client

    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream", metadata: dict[str, str] | None = None) -> dict[str, Any]:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(path)
        try:
            blob.content_type = content_type
            if metadata:
                blob.metadata = metadata
            blob.upload_from_string(data)
            return {
                "path": path,
                "size": len(data),
                "checksum": hashlib.sha256(data).hexdigest(),
                "url": blob.public_url,
            }
        except Exception as exc:
            logger.error(f"GCS put failed for {path}: {exc}")
            raise

    async def get(self, path: str) -> bytes:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(path)
        try:
            return blob.download_as_bytes()
        except Exception as exc:
            logger.error(f"GCS get failed for {path}: {exc}")
            raise

    async def delete(self, path: str) -> bool:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(path)
        try:
            blob.delete()
            return True
        except Exception as exc:
            logger.error(f"GCS delete failed for {path}: {exc}")
            return False

    async def exists(self, path: str) -> bool:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(path)
        try:
            return blob.exists()
        except Exception as exc:
            logger.error(f"GCS exists check failed for {path}: {exc}")
            return False

    async def presigned_url(self, path: str, expiry_seconds: int = 3600, operation: str = "get") -> str:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(path)
        from datetime import timedelta
        try:
            method = "GET" if operation == "get" else "PUT"
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expiry_seconds),
                method=method,
            )
            return url
        except Exception as exc:
            logger.error(f"GCS presigned URL failed for {path}: {exc}")
            raise

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[dict[str, Any]]:
        client = self._get_client()
        bucket = client.bucket(self.bucket)
        try:
            blobs = bucket.list_blobs(prefix=prefix, max_results=max_keys)
            return [
                {
                    "path": blob.name,
                    "size": blob.size,
                    "etag": blob.etag.strip('"') if blob.etag else "",
                    "last_modified": blob.updated.isoformat() if blob.updated else "",
                }
                for blob in blobs
            ]
        except Exception as exc:
            logger.error(f"GCS list failed for prefix {prefix}: {exc}")
            raise
