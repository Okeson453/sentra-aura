"""Tests for the Asset Store."""
from __future__ import annotations

import pytest
from asset_store.models import Asset, ProvenanceRecord
from asset_store.backend import LocalStorageBackend
from asset_store.service import AssetStoreService


@pytest.mark.asyncio
async def test_upload_and_get():
    svc = AssetStoreService()
    asset = await svc.upload("C1", "T1", "image", "test.png", b"fake-image-data", "image/png")
    assert asset.asset_type == "image"
    assert asset.size_bytes == len(b"fake-image-data")

    fetched = await svc.get(asset.asset_id)
    assert fetched is not None
    assert fetched.filename == "test.png"


@pytest.mark.asyncio
async def test_download():
    svc = AssetStoreService()
    asset = await svc.upload("C1", "T1", "image", "test.png", b"data", "image/png")
    data = await svc.download(asset.asset_id)
    assert data == b"data"


@pytest.mark.asyncio
async def test_delete():
    svc = AssetStoreService()
    asset = await svc.upload("C1", "T1", "image", "test.png", b"data", "image/png")
    ok = await svc.delete(asset.asset_id)
    assert ok is True
    assert asset.status == "DELETED"


@pytest.mark.asyncio
async def test_provenance():
    svc = AssetStoreService()
    asset = await svc.upload("C1", "T1", "image", "test.png", b"data", "image/png")
    rec = await svc.add_provenance(asset.asset_id, "edit", "Agent-1", ["SRC-1"])
    assert rec.action == "edit"
    assert rec.agent_id == "Agent-1"

    records = await svc.get_provenance(asset.asset_id)
    assert len(records) == 1


@pytest.mark.asyncio
async def test_list_assets():
    svc = AssetStoreService()
    await svc.upload("C1", "T1", "image", "a.png", b"a", "image/png")
    await svc.upload("C1", "T1", "audio", "b.mp3", b"b", "audio/mpeg")
    await svc.upload("C2", "T1", "image", "c.png", b"c", "image/png")

    imgs = await svc.list_assets(channel_id="C1", asset_type="image")
    assert len(imgs) == 1
    assert imgs[0].filename == "a.png"
