"""Azure Blob Storage backend for SentraAura Asset Store."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from asset_store.backend import StorageBackend

logger = logging.getLogger(__name__)


class AzureStorageBackend(StorageBackend):
    """Azure Blob Storage backend."""

    def __init__(
        self,
        container: str,
        connection_string: str | None = None,
        account_url: str | None = None,
        credential: Any = None,
    ) -> None:
        self.container = container
        self.connection_string = connection_string
        self.account_url = account_url
        self.credential = credential
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from azure.storage.blob import BlobServiceClient
                if self.connection_string:
                    self._client = BlobServiceClient.from_connection_string(self.connection_string)
                else:
                    self._client = BlobServiceClient(account_url=self.account_url, credential=self.credential)
            except ImportError:
                raise RuntimeError("azure-storage-blob is required for Azure backend")
        return self._client

    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream", metadata: dict[str, str] | None = None) -> dict[str, Any]:
        client = self._get_client()
        blob_client = client.get_blob_client(container=self.container, blob=path)
        try:
            blob_client.upload_blob(data, overwrite=True, content_settings={"content_type": content_type}, metadata=metadata)
            return {
                "path": path,
                "size": len(data),
                "checksum": hashlib.sha256(data).hexdigest(),
                "url": blob_client.url,
            }
        except Exception as exc:
            logger.error(f"Azure put failed for {path}: {exc}")
            raise

    async def get(self, path: str) -> bytes:
        client = self._get_client()
        blob_client = client.get_blob_client(container=self.container, blob=path)
        try:
            return blob_client.download_blob().readall()
        except Exception as exc:
            logger.error(f"Azure get failed for {path}: {exc}")
            raise

    async def delete(self, path: str) -> bool:
        client = self._get_client()
        blob_client = client.get_blob_client(container=self.container, blob=path)
        try:
            blob_client.delete_blob()
            return True
        except Exception as exc:
            logger.error(f"Azure delete failed for {path}: {exc}")
            return False

    async def exists(self, path: str) -> bool:
        client = self._get_client()
        blob_client = client.get_blob_client(container=self.container, blob=path)
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    async def presigned_url(self, path: str, expiry_seconds: int = 3600, operation: str = "get") -> str:
        client = self._get_client()
        blob_client = client.get_blob_client(container=self.container, blob=path)
        from datetime import datetime, timedelta
        expiry = datetime.utcnow() + timedelta(seconds=expiry_seconds)
        try:
            permission = "r" if operation == "get" else "w"
            sas_token = blob_client.generate_shared_access_signature(
                permission=permission,
                expiry=expiry,
            )
            return f"{blob_client.url}?{sas_token}"
        except Exception as exc:
            logger.error(f"Azure presigned URL failed for {path}: {exc}")
            raise

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[dict[str, Any]]:
        client = self._get_client()
        container_client = client.get_container_client(self.container)
        try:
            blobs = container_client.list_blobs(name_starts_with=prefix, max_results=max_keys)
            return [
                {
                    "path": blob.name,
                    "size": blob.size,
                    "etag": blob.etag.strip('"') if blob.etag else "",
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else "",
                }
                for blob in blobs
            ]
        except Exception as exc:
            logger.error(f"Azure list failed for prefix {prefix}: {exc}")
            raise
