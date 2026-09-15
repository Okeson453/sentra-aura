"""HTTP client for rights-registry-service (Architecture Content-ID / claims path).

P4-17: never treat missing registry records as cleared rights — fail closed
when the registry returns 404 or is unreachable so takedowns are not skipped.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


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

        When base_url is unset, returns status=unknown (not clear) so unit
        tests must explicitly mock a clear verdict — prevents false clearance.
        """
        if not self.base_url:
            return {
                "asset_id": rights_id,
                "status": "unknown",
                "invoked": True,
                "claims": [],
                "warning": "rights-registry base_url not configured; not treating as cleared",
            }
        # REAL_INTEGRATION: rights-registry-service
        try:
            r = httpx.post(
                f"{self.base_url}/rights/{rights_id}/check",
                json=payload or {},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            logger.error("rights-registry unreachable for %s: %s", rights_id, exc)
            return {
                "asset_id": rights_id,
                "status": "error",
                "invoked": True,
                "claims": [],
                "error": str(exc),
            }
        if r.status_code == 404:
            # Missing record must not be treated as cleared (P4-17)
            return {
                "asset_id": rights_id,
                "status": "not_found",
                "invoked": True,
                "claims": [],
                "message": "asset not in rights-registry — do not mark remediation complete",
            }
        if r.status_code >= 400:
            return {
                "asset_id": rights_id,
                "status": "error",
                "invoked": True,
                "claims": [],
                "http_status": r.status_code,
            }
        data = r.json()
        if isinstance(data, dict):
            data.setdefault("invoked", True)
            return data
        return {"result": data, "invoked": True}

    async def acheck(self, rights_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base_url:
            return {
                "asset_id": rights_id,
                "status": "unknown",
                "invoked": True,
                "claims": [],
                "warning": "rights-registry base_url not configured; not treating as cleared",
            }
        try:
            client = await self._get()
            # REAL_INTEGRATION: rights-registry-service
            r = await client.post(
                f"{self.base_url}/rights/{rights_id}/check",
                json=payload or {},
            )
        except httpx.HTTPError as exc:
            logger.error("rights-registry unreachable for %s: %s", rights_id, exc)
            return {
                "asset_id": rights_id,
                "status": "error",
                "invoked": True,
                "claims": [],
                "error": str(exc),
            }
        if r.status_code == 404:
            return {
                "asset_id": rights_id,
                "status": "not_found",
                "invoked": True,
                "claims": [],
                "message": "asset not in rights-registry — do not mark remediation complete",
            }
        if r.status_code >= 400:
            return {
                "asset_id": rights_id,
                "status": "error",
                "invoked": True,
                "claims": [],
                "http_status": r.status_code,
            }
        data = r.json()
        if isinstance(data, dict):
            data.setdefault("invoked", True)
            return data
        return {"result": data, "invoked": True}
