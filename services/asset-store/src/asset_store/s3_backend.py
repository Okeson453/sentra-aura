"""Amazon S3 storage backend for SentraAura Asset Store.

Supports multipart upload, presigned URLs, and lifecycle policies.
Matches Backend Spec §13.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from asset_store.backend import StorageBackend
from asset_store.models import Asset

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend (AWS S3, MinIO, Wasabi, etc.)."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key: str | None = None,
        secret_key: str | None = None,
        endpoint_url: str | None = None,
        max_part_size: int = 100 * 1024 * 1024,  # 100MB
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint_url = endpoint_url
        self.max_part_size = max_part_size
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
                session = boto3.Session(
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
                config = Config(
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    connect_timeout=10,
                    read_timeout=30,
                )
                self._client = session.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    config=config,
                )
            except ImportError:
                raise RuntimeError("boto3 is required for S3 backend")
        return self._client

    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream", metadata: dict[str, str] | None = None) -> dict[str, Any]:
        client = self._get_client()
        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata
        try:
            client.put_object(Bucket=self.bucket, Key=path, Body=data, **extra_args)
            return {
                "path": path,
                "size": len(data),
                "checksum": hashlib.sha256(data).hexdigest(),
                "url": f"s3://{self.bucket}/{path}",
            }
        except Exception as exc:
            logger.error(f"S3 put failed for {path}: {exc}")
            raise

    async def get(self, path: str) -> bytes:
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read()
        except Exception as exc:
            logger.error(f"S3 get failed for {path}: {exc}")
            raise

    async def delete(self, path: str) -> bool:
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception as exc:
            logger.error(f"S3 delete failed for {path}: {exc}")
            return False

    async def exists(self, path: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket, Key=path)
            return True
        except client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    async def presigned_url(self, path: str, expiry_seconds: int = 3600, operation: str = "get") -> str:
        client = self._get_client()
        method = "get_object" if operation == "get" else "put_object"
        try:
            url = client.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expiry_seconds,
            )
            return url
        except Exception as exc:
            logger.error(f"S3 presigned URL failed for {path}: {exc}")
            raise

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[dict[str, Any]]:
        client = self._get_client()
        try:
            response = client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, MaxKeys=max_keys)
            return [
                {
                    "path": obj["Key"],
                    "size": obj["Size"],
                    "etag": obj["ETag"].strip('"'),
                    "last_modified": obj["LastModified"].isoformat(),
                }
                for obj in response.get("Contents", [])
            ]
        except Exception as exc:
            logger.error(f"S3 list failed for prefix {prefix}: {exc}")
            raise

    async def multipart_upload(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
        """Upload large files using multipart S3 upload."""
        client = self._get_client()
        import io
        part_size = self.max_part_size
        total_size = len(data)

        try:
            mpu = client.create_multipart_upload(Bucket=self.bucket, Key=path, ContentType=content_type)
            upload_id = mpu["UploadId"]
            parts: list[dict[str, Any]] = []
            part_number = 1

            stream = io.BytesIO(data)
            while True:
                chunk = stream.read(part_size)
                if not chunk:
                    break
                response = client.upload_part(
                    Bucket=self.bucket,
                    Key=path,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append({"PartNumber": part_number, "ETag": response["ETag"]})
                part_number += 1

            client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=path,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            return {
                "path": path,
                "size": total_size,
                "checksum": hashlib.sha256(data).hexdigest(),
                "parts": len(parts),
            }
        except Exception as exc:
            logger.error(f"S3 multipart upload failed for {path}: {exc}")
            # Abort multipart upload on failure
            try:
                client.abort_multipart_upload(Bucket=self.bucket, Key=path, UploadId=upload_id)
            except Exception:
                pass
            raise
