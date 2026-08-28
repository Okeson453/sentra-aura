"""Async HTTP test client for SentraAura services."""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI


class AsyncTestClient:
    """Async HTTP client for testing FastAPI services."""

    def __init__(self, app: FastAPI, *, base_url: str = "http://test") -> None:
        self.client = httpx.AsyncClient(app=app, base_url=base_url)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.post(path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.put(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.delete(path, **kwargs)

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> "AsyncTestClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
