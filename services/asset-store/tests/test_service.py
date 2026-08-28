"""Tests for asset store."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from asset_store.models import Asset, ProvenanceRecord
from asset_store.service import AssetStoreService
from asset_store.backend import LocalStorageBackend
from asset_store.virus_scanner import SignatureScanner, ClamAVScanner, ScanResult, AsyncScanQueue


class TestAssetStoreService:
    @pytest.mark.asyncio
    async def test_upload_asset(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        asset = await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="test.mp4", data=b"test video data",
            content_type="video/mp4", created_by="user-1",
        )
        assert asset.asset_type == "VIDEO"
        assert asset.filename == "test.mp4"
        assert asset.size_bytes == len(b"test video data")
        assert asset.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_upload_with_virus_detection(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        # EICAR test signature
        eicar = b"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        with pytest.raises(ValueError, match="Virus scan failed"):
            await service.upload(
                channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
                filename="virus.txt", data=eicar, skip_scan=False,
            )

    @pytest.mark.asyncio
    async def test_upload_skip_scan(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        eicar = b"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        asset = await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="virus.txt", data=eicar, skip_scan=True,
        )
        assert asset.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_download_asset(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="test.mp4", data=b"test data",
        )
        assets = await service.list_assets(channel_id="ch-1")
        data = await service.download(assets[0].asset_id)
        assert data == b"test data"

    @pytest.mark.asyncio
    async def test_delete_asset(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        asset = await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="test.mp4", data=b"test data",
        )
        ok = await service.delete(asset.asset_id)
        assert ok is True
        assert asset.status == "DELETED"

    @pytest.mark.asyncio
    async def test_list_assets_filtered(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        await service.upload(channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO", filename="v1.mp4", data=b"v1")
        await service.upload(channel_id="ch-1", tenant_id="t-1", asset_type="THUMBNAIL", filename="t1.jpg", data=b"t1")
        await service.upload(channel_id="ch-2", tenant_id="t-1", asset_type="VIDEO", filename="v2.mp4", data=b"v2")

        ch1_video = await service.list_assets(channel_id="ch-1", asset_type="VIDEO")
        assert len(ch1_video) == 1
        assert ch1_video[0].filename == "v1.mp4"

    @pytest.mark.asyncio
    async def test_provenance(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        asset = await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="test.mp4", data=b"test data",
        )
        await service.add_provenance(asset.asset_id, "edit", "agent-1", metadata={"tool": "ffmpeg"})
        records = await service.get_provenance(asset.asset_id)
        assert len(records) == 1
        assert records[0].action == "edit"

    @pytest.mark.asyncio
    async def test_scan_asset(self):
        service = AssetStoreService(backend=LocalStorageBackend(), scanner=SignatureScanner())
        asset = await service.upload(
            channel_id="ch-1", tenant_id="t-1", asset_type="VIDEO",
            filename="test.mp4", data=b"clean data",
        )
        result = await service.scan_asset(asset.asset_id)
        assert result.clean is True


class TestVirusScanner:
    @pytest.mark.asyncio
    async def test_signature_scanner_clean(self):
        scanner = SignatureScanner()
        result = await scanner.scan(b"clean data", "clean.txt")
        assert result.clean is True

    @pytest.mark.asyncio
    async def test_signature_scanner_detects_eicar(self):
        scanner = SignatureScanner()
        eicar = b"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        result = await scanner.scan(eicar, "test.txt")
        assert result.clean is False
        assert result.threat == "eicar_test"

    @pytest.mark.asyncio
    async def test_signature_scanner_detects_executable(self):
        scanner = SignatureScanner()
        result = await scanner.scan(b"MZ header fake exe", "malware.exe")
        assert result.clean is False
        assert result.threat == "executable_in_disguise"

    @pytest.mark.asyncio
    async def test_clamav_fallback(self):
        scanner = ClamAVScanner()
        # clamd is not installed in test env; ImportError triggers fallback
        result = await scanner.scan(b"test", "test.txt")
        assert result.scanner == "signature"


class TestAsyncScanQueue:
    @pytest.mark.asyncio
    async def test_scan_batch(self):
        scanner = SignatureScanner()
        queue = AsyncScanQueue(scanner, max_concurrent=2)
        items = [
            ("asset-1", b"clean", "clean.txt"),
            ("asset-2", b"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*", "virus.txt"),
            ("asset-3", b"also clean", "clean2.txt"),
        ]
        results = await queue.scan_batch(items)
        assert results["asset-1"].clean is True
        assert results["asset-2"].clean is False
        assert results["asset-3"].clean is True
