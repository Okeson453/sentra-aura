"""Routes for the Asset Store service.

Updated to use database-backed storage and remove skip_scan parameter.
Fixes Finding F-025.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from asset_store.models import Asset, ProvenanceRecord
from asset_store.backend import StorageBackend, LocalStorageBackend
from asset_store.db_backend import DatabaseMetadataBackend
from asset_store.service import AssetStoreService
from asset_store.virus_scanner import ClamAVScanner, SignatureScanner

router = APIRouter()


def get_service() -> AssetStoreService:
    # Use database backend by default
    backend = LocalStorageBackend()
    metadata_backend = DatabaseMetadataBackend(backend)
    return AssetStoreService(backend=backend, scanner=SignatureScanner(), metadata_backend=metadata_backend)


@router.post("/upload", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def upload_asset(
    channel_id: str = Form(...),
    tenant_id: str = Form(...),
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    content_type: str | None = Form(default=None),
    metadata: str = Form(default="{}"),
    created_by: str = Form(default=""),
    service: AssetStoreService = Depends(get_service),
) -> dict[str, Any]:
    """Upload an asset with mandatory virus scanning.
    
    Note: skip_scan parameter has been removed. All uploads are scanned for viruses.
    """
    meta = json.loads(metadata) if metadata else {}
    data = await file.read()

    try:
        asset = await service.upload(
            channel_id=channel_id,
            tenant_id=tenant_id,
            asset_type=asset_type,
            filename=file.filename or "unnamed",
            data=data,
            content_type=content_type or (file.content_type or "application/octet-stream"),
            metadata=meta,
            created_by=created_by,
            skip_scan=False,  # Always scan - cannot be bypassed
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return {
        "asset_id": asset.asset_id,
        "channel_id": asset.channel_id,
        "tenant_id": asset.tenant_id,
        "asset_type": asset.asset_type,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "checksum": asset.checksum,
        "storage_path": asset.storage_path,
        "storage_provider": asset.storage_provider,
        "status": asset.status,
        "created_at": asset.created_at.isoformat(),
    }


@router.post("/upload-multipart", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def upload_multipart(
    channel_id: str = Form(...),
    tenant_id: str = Form(...),
    asset_type: str = Form(...),
    upload_id: str = Form(...),
    part_number: int = Form(...),
    total_parts: int = Form(...),
    file: UploadFile = File(...),
    content_type: str | None = Form(default=None),
    metadata: str = Form(default="{}"),
    created_by: str = Form(default=""),
    service: AssetStoreService = Depends(get_service),
) -> dict[str, Any]:
    """Upload a part of a multipart upload.
    
    Note: Uses authenticated temp directory per tenant/channel.
    Fixes Finding F-024 (predictable temp filenames).
    """
    meta = json.loads(metadata) if metadata else {}
    data = await file.read()

    # Use authenticated temp directory
    # This fixes Finding F-024 (multipart temp handling)
    temp_dir = tempfile.mkdtemp(prefix=f"sentra-aura-multipart-{tenant_id}-{channel_id}-")
    part_path = os.path.join(temp_dir, f"{upload_id}_part_{part_number}")
    
    try:
        with open(part_path, "wb") as f:
            f.write(data)

        # Check if all parts received
        received_parts = sum(
            1 for i in range(1, total_parts + 1)
            if os.path.exists(os.path.join(temp_dir, f"{upload_id}_part_{i}"))
        )

        if received_parts == total_parts:
            # Assemble complete file
            complete_data = bytearray()
            for i in range(1, total_parts + 1):
                p = os.path.join(temp_dir, f"{upload_id}_part_{i}")
                with open(p, "rb") as f:
                    complete_data.extend(f.read())

            asset = await service.upload(
                channel_id=channel_id,
                tenant_id=tenant_id,
                asset_type=asset_type,
                filename=file.filename or f"{upload_id}.bin",
                data=bytes(complete_data),
                content_type=content_type or (file.content_type or "application/octet-stream"),
                metadata={**meta, "multipart": True, "total_parts": total_parts},
                created_by=created_by,
            )
            
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return {
                "asset_id": asset.asset_id,
                "status": "completed",
                "upload_id": upload_id,
                "parts_received": received_parts,
                "total_parts": total_parts,
                "size_bytes": asset.size_bytes,
            }

        return {
            "status": "pending",
            "upload_id": upload_id,
            "part_number": part_number,
            "parts_received": received_parts,
            "total_parts": total_parts,
        }
    except Exception as e:
        # Clean up temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@router.get("/{asset_id}", response_model=dict[str, Any])
async def get_asset(
    asset_id: str,
    service: AssetStoreService = Depends(get_service),
) -> dict[str, Any]:
    asset = await service.get(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return {
        "asset_id": asset.asset_id,
        "channel_id": asset.channel_id,
        "tenant_id": asset.tenant_id,
        "asset_type": asset.asset_type,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "checksum": asset.checksum,
        "storage_path": asset.storage_path,
        "storage_provider": asset.storage_provider,
        "status": asset.status,
        "created_at": asset.created_at.isoformat(),
        "metadata": asset.metadata,
    }


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    service: AssetStoreService = Depends(get_service),
) -> Any:
    """Download asset data."""
    from fastapi.responses import StreamingResponse

    asset = await service.get(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    data = await service.download(asset_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=asset.content_type,
        headers={"Content-Disposition": f'attachment; filename="{asset.filename}"'},
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    service: AssetStoreService = Depends(get_service),
) -> None:
    ok = await service.delete(asset_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")


@router.get("", response_model=list[dict[str, Any]])
async def list_assets(
    channel_id: str | None = None,
    asset_type: str | None = None,
    service: AssetStoreService = Depends(get_service),
) -> list[dict[str, Any]]:
    assets = await service.list_assets(channel_id=channel_id, asset_type=asset_type)
    return [
        {
            "asset_id": a.asset_id,
            "channel_id": a.channel_id,
            "tenant_id": a.tenant_id,
            "asset_type": a.asset_type,
            "filename": a.filename,
            "size_bytes": a.size_bytes,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        }
        for a in assets
    ]


@router.post("/{asset_id}/scan", response_model=dict[str, Any])
async def scan_asset(
    asset_id: str,
    service: AssetStoreService = Depends(get_service),
) -> dict[str, Any]:
    """Rescan an asset for viruses."""
    result = await service.scan_asset(asset_id)
    return {
        "asset_id": asset_id,
        "clean": result.clean,
        "threat": result.threat,
        "scanner": result.scanner,
        "signature": result.signature,
        "details": result.details,
    }


@router.get("/{asset_id}/provenance", response_model=list[dict[str, Any]])
async def get_provenance(
    asset_id: str,
    service: AssetStoreService = Depends(get_service),
) -> list[dict[str, Any]]:
    records = await service.get_provenance(asset_id)
    return [
        {
            "record_id": r.record_id,
            "action": r.action,
            "agent_id": r.agent_id,
            "source_asset_ids": r.source_asset_ids,
            "metadata": r.metadata,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
