"""Select storage backend from configuration (Backend §13 / Architecture object storage).

Previously LocalStorageBackend was hardcoded in routes/service regardless of
STORAGE_BACKEND — production data would not survive pod restarts. This factory
wires S3 / GCS / Azure when configured, else local for dev.
"""
from __future__ import annotations

import logging
from typing import Any

from asset_store.backend import LocalStorageBackend, StorageBackend
from asset_store.config import Settings, get_settings

logger = logging.getLogger(__name__)


def create_storage_backend(settings: Settings | None = None) -> StorageBackend:
    """Instantiate the configured storage backend."""
    settings = settings or get_settings()
    name = (settings.storage_backend or "local").strip().lower()

    if name in ("s3", "minio", "aws"):
        if not settings.s3_bucket:
            logger.warning("STORAGE_BACKEND=%s but S3_BUCKET unset; falling back to local", name)
            return LocalStorageBackend()
        from asset_store.s3_backend import S3StorageBackend

        endpoint = getattr(settings, "s3_endpoint_url", None)
        return S3StorageBackend(
            bucket=settings.s3_bucket,
            region=settings.s3_region or "us-east-1",
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            endpoint_url=endpoint,
        )

    if name in ("gcs", "google", "gcp"):
        if not settings.gcs_bucket:
            logger.warning("STORAGE_BACKEND=gcs but GCS_BUCKET unset; falling back to local", name)
            return LocalStorageBackend()
        from asset_store.gcs_backend import GCSStorageBackend

        project = getattr(settings, "gcs_project_id", None)
        creds = getattr(settings, "gcs_credentials_path", None)
        return GCSStorageBackend(
            bucket=settings.gcs_bucket,
            project_id=project,
            credentials_path=creds,
        )

    if name in ("azure", "blob"):
        container = getattr(settings, "azure_container", None) or getattr(
            settings, "azure_blob_container", None
        )
        conn = getattr(settings, "azure_connection_string", None)
        if not container:
            logger.warning("STORAGE_BACKEND=azure but container unset; falling back to local")
            return LocalStorageBackend()
        from asset_store.azure_backend import AzureStorageBackend

        return AzureStorageBackend(
            container=container,
            connection_string=conn,
            account_url=getattr(settings, "azure_account_url", None),
        )

    if name not in ("local", "filesystem", "fs", ""):
        logger.warning("Unknown STORAGE_BACKEND=%r; using local", name)
    return LocalStorageBackend()
