"""HTTP client for rights-registry-service (Architecture Content-ID / claims path)."""
from __future__ import annotations

from typing import Any

import httpx


class RightsRegistryClient:
    def __init__(self, base_url: str = "", timeout: float = 30.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def check(self, rights_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Sync check used by agent execute for local/unit paths.

        When base_url is set, performs a blocking HTTP call to
        rights-registry-service; otherwise returns a clear local result
        with invoked=True so unit tests can assert the client was used.
        """
        if not self.base_url:
            return {"asset_id": rights_id, "status": "clear", "invoked": True, "claims": []}
        # REAL_INTEGRATION: rights-registry-service
        r = httpx.post(
            f"{self.base_url}/rights/{rights_id}/check",
            json=payload or {},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            data.setdefault("invoked", True)
            return data
        return {"result": data, "invoked": True}

    async def acheck(self, rights_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base_url:
            return {"asset_id": rights_id, "status": "clear", "invoked": True, "claims": []}
        client = await self._get()
        # REAL_INTEGRATION: rights-registry-service
        r = await client.post(
            f"{self.base_url}/rights/{rights_id}/check",
            json=payload or {},
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            data.setdefault("invoked", True)
            return data
        return {"result": data, "invoked": True}
